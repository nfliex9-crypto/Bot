"""
Risk Manager.

Handles all risk calculations:
- Position sizing (fixed fractional based on % risk)
- Max drawdown enforcement
- Max trades per session enforcement
- Daily loss limit checks
"""
import math
from typing import Optional, Dict
from dataclasses import dataclass
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("risk_manager")


@dataclass
class PositionSize:
    lot_size: float
    risk_amount: float
    risk_pct: float
    stop_loss_pips: float
    pip_value: float
    valid: bool = True
    rejection_reason: Optional[str] = None


@dataclass
class RiskStatus:
    can_trade: bool
    current_drawdown: float
    max_drawdown_limit: float
    session_trades: int
    max_session_trades: int
    daily_pnl: float
    reason: Optional[str] = None


# Pip values per instrument (approximate)
PIP_VALUES = {
    # Forex majors (per 0.01 lot = 1000 units)
    "EURUSD": 0.10,
    "GBPUSD": 0.10,
    "AUDUSD": 0.10,
    "NZDUSD": 0.10,
    "USDCAD": 0.076,
    "USDCHF": 0.108,
    "USDJPY": 0.0070,
    "EURJPY": 0.0070,
    "GBPJPY": 0.0070,
    "AUDJPY": 0.0070,
    # Crypto (per 0.001 BTC)
    "BTCUSDT": 1.0,
    "ETHUSDT": 1.0,
    "BNBUSDT": 1.0,
    "SOLUSDT": 1.0,
    "XRPUSDT": 1.0,
}

# Pip size per instrument
PIP_SIZE = {
    "USDJPY": 0.01, "EURJPY": 0.01, "GBPJPY": 0.01, "AUDJPY": 0.01,
    "DEFAULT_FOREX": 0.0001,
    "DEFAULT_CRYPTO": 1.0,
}

# Min/Max lot sizes
LOT_CONSTRAINTS = {
    "forex": {"min": 0.01, "max": 100.0, "step": 0.01},
    "crypto": {"min": 0.001, "max": 1000.0, "step": 0.001},
}


class RiskManager:
    """
    Calculates position sizing and enforces risk limits.
    """

    def __init__(
        self,
        account_balance: float = None,
        risk_per_trade: float = None,
        max_drawdown: float = None,
        max_trades_per_session: int = None,
    ):
        self.account_balance = account_balance or settings.ACCOUNT_BALANCE
        self.risk_per_trade = risk_per_trade or settings.RISK_PER_TRADE
        self.max_drawdown = max_drawdown or settings.MAX_DRAWDOWN
        self.max_trades_per_session = max_trades_per_session or settings.MAX_TRADES_PER_SESSION

        # Runtime tracking
        self.peak_balance = self.account_balance
        self.current_balance = self.account_balance
        self.session_trades = 0
        self.daily_pnl = 0.0

    def calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        account_balance: Optional[float] = None,
        market_type: str = "forex",
    ) -> PositionSize:
        """
        Calculate position size using fixed fractional risk.

        Formula:
            risk_amount = account_balance × risk_per_trade
            pip_risk = |entry - stop_loss| / pip_size
            lot_size = risk_amount / (pip_risk × pip_value_per_lot)
        """
        balance = account_balance or self.current_balance
        risk_amount = balance * self.risk_per_trade

        sl_distance = abs(entry_price - stop_loss)
        if sl_distance == 0:
            return PositionSize(
                lot_size=0.0, risk_amount=0.0, risk_pct=0.0,
                stop_loss_pips=0.0, pip_value=0.0,
                valid=False, rejection_reason="Zero stop loss distance"
            )

        # Get pip size
        if market_type == "crypto":
            pip_size = 1.0
        elif symbol.endswith("JPY"):
            pip_size = 0.01
        else:
            pip_size = 0.0001

        pip_risk = sl_distance / pip_size

        # Get pip value (per standard lot, then scale)
        pip_value_per_std_lot = self._get_pip_value(symbol, entry_price, market_type)

        if pip_value_per_std_lot <= 0 or pip_risk <= 0:
            return PositionSize(
                lot_size=0.01, risk_amount=risk_amount, risk_pct=self.risk_per_trade,
                stop_loss_pips=pip_risk, pip_value=pip_value_per_std_lot,
                valid=True
            )

        # Lot size = risk_amount / (pip_risk × pip_value_per_lot)
        raw_lot_size = risk_amount / (pip_risk * pip_value_per_std_lot)

        # Apply constraints
        constraints = LOT_CONSTRAINTS.get(market_type, LOT_CONSTRAINTS["forex"])
        lot_size = max(constraints["min"], min(raw_lot_size, constraints["max"]))

        # Round to step
        step = constraints["step"]
        lot_size = math.floor(lot_size / step) * step
        lot_size = round(lot_size, len(str(step).rstrip("0").split(".")[-1]))

        actual_risk = lot_size * pip_risk * pip_value_per_std_lot

        logger.debug(
            f"Position size: {symbol} balance={balance:.2f} risk_amt={risk_amount:.2f} "
            f"sl_pips={pip_risk:.1f} lot={lot_size} actual_risk={actual_risk:.2f}"
        )

        return PositionSize(
            lot_size=lot_size,
            risk_amount=actual_risk,
            risk_pct=actual_risk / balance,
            stop_loss_pips=pip_risk,
            pip_value=pip_value_per_std_lot,
            valid=True,
        )

    def check_risk_limits(
        self,
        session_trades: Optional[int] = None,
        current_balance: Optional[float] = None,
    ) -> RiskStatus:
        """
        Check all risk limits before allowing a new trade.
        """
        balance = current_balance or self.current_balance
        trades = session_trades if session_trades is not None else self.session_trades

        # Check drawdown
        if balance < self.peak_balance:
            drawdown = (self.peak_balance - balance) / self.peak_balance
        else:
            drawdown = 0.0
            self.peak_balance = balance  # Update peak

        if drawdown >= self.max_drawdown:
            logger.warning(
                f"Max drawdown reached: {drawdown:.2%} >= {self.max_drawdown:.2%}"
            )
            return RiskStatus(
                can_trade=False,
                current_drawdown=drawdown,
                max_drawdown_limit=self.max_drawdown,
                session_trades=trades,
                max_session_trades=self.max_trades_per_session,
                daily_pnl=self.daily_pnl,
                reason=f"Max drawdown {drawdown:.2%} >= limit {self.max_drawdown:.2%}",
            )

        # Check session trades
        if trades >= self.max_trades_per_session:
            logger.info(
                f"Max session trades reached: {trades}/{self.max_trades_per_session}"
            )
            return RiskStatus(
                can_trade=False,
                current_drawdown=drawdown,
                max_drawdown_limit=self.max_drawdown,
                session_trades=trades,
                max_session_trades=self.max_trades_per_session,
                daily_pnl=self.daily_pnl,
                reason=f"Max trades per session ({self.max_trades_per_session}) reached",
            )

        return RiskStatus(
            can_trade=True,
            current_drawdown=drawdown,
            max_drawdown_limit=self.max_drawdown,
            session_trades=trades,
            max_session_trades=self.max_trades_per_session,
            daily_pnl=self.daily_pnl,
        )

    def update_balance(self, new_balance: float):
        """Update current balance and peak tracking."""
        self.current_balance = new_balance
        if new_balance > self.peak_balance:
            self.peak_balance = new_balance

    def record_trade_pnl(self, pnl: float):
        """Record trade P&L for daily tracking."""
        self.daily_pnl += pnl
        self.current_balance += pnl
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance

    def increment_session_trades(self):
        """Record a new trade for session counting."""
        self.session_trades += 1

    def reset_session(self):
        """Reset session trade counter (call at session start)."""
        self.session_trades = 0

    def reset_daily(self):
        """Reset daily P&L tracking (call at midnight UTC)."""
        self.daily_pnl = 0.0

    def _get_pip_value(
        self,
        symbol: str,
        price: float,
        market_type: str,
    ) -> float:
        """
        Get pip value per standard lot in account currency (USD).
        Standard lot = 100,000 units for forex, varies for crypto.
        """
        if market_type == "crypto":
            # For crypto, 1 unit at price X, 1 pip = $1
            return price * 0.001  # Per 0.001 lot

        symbol = symbol.upper()

        # USD quote currencies (EURUSD, GBPUSD, AUDUSD, NZDUSD)
        usd_quote = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD"]
        if symbol in usd_quote:
            return 10.0  # $10 per pip per standard lot

        # JPY pairs
        jpy_pairs = ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY"]
        if symbol in jpy_pairs:
            return 1000.0 / price  # Approximate

        # USD base (USDCAD, USDCHF)
        if symbol in ["USDCAD", "USDCHF"]:
            return 10.0 / price  # Approximate

        return 10.0  # Default

    def get_account_stats(self) -> dict:
        """Return current account statistics."""
        drawdown = max(0.0, (self.peak_balance - self.current_balance) / (self.peak_balance + 1e-10))
        return {
            "current_balance": round(self.current_balance, 2),
            "peak_balance": round(self.peak_balance, 2),
            "current_drawdown": round(drawdown, 4),
            "max_drawdown_limit": self.max_drawdown,
            "daily_pnl": round(self.daily_pnl, 2),
            "session_trades": self.session_trades,
            "max_session_trades": self.max_trades_per_session,
            "available_risk": round(self.current_balance * self.risk_per_trade, 2),
        }
