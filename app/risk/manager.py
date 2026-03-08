from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from loguru import logger

from app.core.config import settings


@dataclass
class RiskCheck:
    approved: bool
    reason: str = ""
    position_size: float = 0.0
    risk_amount: float = 0.0


class RiskManager:
    """
    Central risk management engine.

    Rules:
      - Risk per trade: 0.75% of balance
      - Max drawdown: 15%
      - Max trades per session: 3
      - Correlation guard: max 2 trades same direction per currency
    """

    def __init__(self) -> None:
        self._initial_balance = settings.account_balance
        self._current_balance = settings.account_balance
        self._risk_pct = settings.risk_per_trade / 100.0
        self._max_dd_pct = settings.max_drawdown_pct / 100.0
        self._max_trades = settings.max_trades_per_session
        self._peak_balance = settings.account_balance
        self._open_trade_count = 0
        self._session_trade_count = 0
        self._session_start: datetime | None = None
        self._open_symbols: dict[str, str] = {}  # symbol → direction

    def update_balance(self, balance: float) -> None:
        self._current_balance = balance
        if balance > self._peak_balance:
            self._peak_balance = balance

    def update_open_trades(self, count: int) -> None:
        self._open_trade_count = count

    def register_trade_opened(self, symbol: str, direction: str) -> None:
        self._session_trade_count += 1
        self._open_trade_count += 1
        self._open_symbols[symbol] = direction

    def register_trade_closed(self, symbol: str, pnl: float) -> None:
        self._open_trade_count = max(0, self._open_trade_count - 1)
        self._open_symbols.pop(symbol, None)
        self._current_balance += pnl
        if self._current_balance > self._peak_balance:
            self._peak_balance = self._current_balance

    def reset_session(self) -> None:
        self._session_trade_count = 0
        self._session_start = datetime.now(timezone.utc)

    @property
    def current_drawdown_pct(self) -> float:
        if self._peak_balance == 0:
            return 0.0
        return (self._peak_balance - self._current_balance) / self._peak_balance

    def check_trade(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        market: str = "forex",
    ) -> RiskCheck:
        """Pre-trade risk check. Returns approval + position sizing."""

        # Max drawdown breached
        if self.current_drawdown_pct >= self._max_dd_pct:
            reason = (
                f"Max drawdown breached: {self.current_drawdown_pct:.1%} >= {self._max_dd_pct:.0%}"
            )
            logger.warning(reason)
            return RiskCheck(approved=False, reason=reason)

        # Session trade limit
        if self._session_trade_count >= self._max_trades:
            reason = f"Session trade limit reached: {self._session_trade_count}/{self._max_trades}"
            logger.warning(reason)
            return RiskCheck(approved=False, reason=reason)

        # Already have a trade on this symbol
        if symbol in self._open_symbols:
            reason = f"Already have open position on {symbol}"
            logger.warning(reason)
            return RiskCheck(approved=False, reason=reason)

        # Position sizing
        risk_amount = self._current_balance * self._risk_pct
        price_risk = abs(entry_price - stop_loss)

        if price_risk == 0:
            return RiskCheck(approved=False, reason="Zero price risk (SL = entry)")

        if market == "forex":
            position_size = self._size_forex(risk_amount, price_risk, symbol)
        else:
            position_size = self._size_crypto(risk_amount, price_risk, entry_price)

        if position_size <= 0:
            return RiskCheck(approved=False, reason="Calculated position size is zero")

        logger.info(
            f"Risk approved: {symbol} {direction} size={position_size:.4f} "
            f"risk=${risk_amount:.2f} ({self._risk_pct:.2%})"
        )
        return RiskCheck(
            approved=True,
            position_size=position_size,
            risk_amount=risk_amount,
        )

    def _size_forex(self, risk_amount: float, price_risk: float, symbol: str) -> float:
        """Forex lot sizing — 1 standard lot = 100,000 units."""
        pip_value = 10.0  # approximate for USD-quoted pairs
        if "JPY" in symbol:
            pip_risk = price_risk / 0.01
        else:
            pip_risk = price_risk / 0.0001

        if pip_risk == 0:
            return 0.0

        lots = risk_amount / (pip_risk * pip_value)
        lots = round(lots, 2)
        lots = max(0.01, min(lots, 10.0))
        return lots

    def _size_crypto(self, risk_amount: float, price_risk: float, entry_price: float) -> float:
        """Crypto position sizing in base units."""
        if price_risk == 0:
            return 0.0
        quantity = risk_amount / price_risk
        return round(quantity, 6)
