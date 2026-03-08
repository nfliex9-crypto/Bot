from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Tuple

from config.settings import settings
from core.enums import Direction, Market, TradeStatus
from core.models import AccountState, TradeRecord, TradeSignal
from database.repository import TradeRepository

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Enforces:
      - Per-trade risk (0.75% of balance)
      - Max drawdown (15%)
      - Max trades per session (3)
      - Position sizing based on SL distance
      - Break-even after TP1
    """

    def __init__(self, repo: TradeRepository) -> None:
        self._repo = repo
        self.account = AccountState(
            balance=settings.account_balance,
            equity=settings.account_balance,
            initial_balance=settings.account_balance,
            peak_balance=settings.account_balance,
        )

    async def can_trade(self) -> Tuple[bool, str]:
        if self.account.current_drawdown_pct >= settings.max_drawdown_pct:
            return False, f"Max drawdown reached: {self.account.current_drawdown_pct:.2f}%"

        session_count = await self._repo.get_session_trade_count()
        if session_count >= settings.max_trades_per_session:
            return False, f"Max session trades reached: {session_count}"

        open_trades = await self._repo.get_open_trades()
        if len(open_trades) >= settings.max_trades_per_session:
            return False, f"Max open trades reached: {len(open_trades)}"

        return True, ""

    def calculate_position_size(
        self, signal: TradeSignal, market: Market
    ) -> float:
        risk_amount = self.account.balance * (settings.risk_per_trade / 100)
        sl_distance = abs(signal.entry_price - signal.stop_loss)

        if sl_distance <= 0:
            return 0.0

        if market == Market.FOREX:
            pip_value = self._get_pip_value(signal.symbol)
            sl_pips = sl_distance / pip_value
            if sl_pips <= 0:
                return 0.0
            lot_size = risk_amount / (sl_pips * self._pip_cost(signal.symbol))
            lot_size = round(lot_size, 2)
            lot_size = max(0.01, min(lot_size, 10.0))
            return lot_size

        else:
            position_size = risk_amount / sl_distance
            return round(position_size, 6)

    def validate_signal(self, signal: TradeSignal) -> Tuple[bool, str]:
        if signal.risk_reward < settings.min_rr_ratio:
            return False, f"R:R too low: {signal.risk_reward:.2f} < {settings.min_rr_ratio}"

        sl_distance = abs(signal.entry_price - signal.stop_loss)
        if sl_distance <= 0:
            return False, "Invalid SL distance"

        if signal.direction == Direction.LONG:
            if signal.stop_loss >= signal.entry_price:
                return False, "Long SL must be below entry"
            if signal.tp1 <= signal.entry_price:
                return False, "Long TP1 must be above entry"
        else:
            if signal.stop_loss <= signal.entry_price:
                return False, "Short SL must be above entry"
            if signal.tp1 >= signal.entry_price:
                return False, "Short TP1 must be below entry"

        return True, ""

    def create_trade_record(
        self, signal: TradeSignal, position_size: float
    ) -> TradeRecord:
        risk_amount = self.account.balance * (settings.risk_per_trade / 100)
        return TradeRecord(
            signal_id=signal.id,
            symbol=signal.symbol,
            market=signal.market,
            direction=signal.direction,
            status=TradeStatus.OPEN,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            tp1=signal.tp1,
            tp2=signal.tp2,
            tp3=signal.tp3,
            position_size=position_size,
            risk_amount=risk_amount,
            confidence=signal.confidence,
            opened_at=datetime.utcnow(),
        )

    def update_account_pnl(self, trade: TradeRecord) -> None:
        self.account.total_pnl += trade.pnl
        self.account.balance += trade.pnl
        self.account.equity = self.account.balance

        if trade.pnl > 0:
            self.account.winning_trades += 1
        elif trade.pnl < 0:
            self.account.losing_trades += 1

        self.account.total_trades += 1
        self.account.peak_balance = max(self.account.peak_balance, self.account.balance)

        drawdown = (self.account.peak_balance - self.account.balance) / self.account.peak_balance * 100
        self.account.current_drawdown_pct = drawdown
        self.account.max_drawdown = max(self.account.max_drawdown, drawdown)
        self.account.last_updated = datetime.utcnow()

    def check_breakeven(self, trade: TradeRecord, current_price: float) -> Optional[float]:
        """Returns new SL (at entry) if TP1 is hit and BE not yet set."""
        if trade.breakeven_set or not settings.breakeven_after_tp1:
            return None

        if trade.direction == Direction.LONG and current_price >= trade.tp1:
            return trade.entry_price
        elif trade.direction == Direction.SHORT and current_price <= trade.tp1:
            return trade.entry_price
        return None

    def check_tp_hits(
        self, trade: TradeRecord, current_price: float
    ) -> list[str]:
        """Returns list of TPs just hit."""
        hits = []
        if trade.direction == Direction.LONG:
            if not trade.tp1_hit and current_price >= trade.tp1:
                hits.append("tp1")
            if not trade.tp2_hit and current_price >= trade.tp2:
                hits.append("tp2")
            if not trade.tp3_hit and current_price >= trade.tp3:
                hits.append("tp3")
        else:
            if not trade.tp1_hit and current_price <= trade.tp1:
                hits.append("tp1")
            if not trade.tp2_hit and current_price <= trade.tp2:
                hits.append("tp2")
            if not trade.tp3_hit and current_price <= trade.tp3:
                hits.append("tp3")
        return hits

    def check_stop_loss(self, trade: TradeRecord, current_price: float) -> bool:
        if trade.direction == Direction.LONG:
            return current_price <= trade.stop_loss
        else:
            return current_price >= trade.stop_loss

    @staticmethod
    def _get_pip_value(symbol: str) -> float:
        jpy_pairs = ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "CHFJPY", "NZDJPY"]
        upper = symbol.upper().replace("/", "")
        if any(upper.endswith(j[-3:]) for j in jpy_pairs) or upper in jpy_pairs:
            return 0.01
        return 0.0001

    @staticmethod
    def _pip_cost(symbol: str) -> float:
        """Approximate cost per pip for 1 standard lot (100k units)."""
        jpy_pairs = ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY"]
        upper = symbol.upper().replace("/", "")
        if any(upper.endswith(j[-3:]) for j in jpy_pairs) or upper in jpy_pairs:
            return 6.5
        return 10.0
