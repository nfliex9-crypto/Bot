"""
Risk management engine.

Enforces:
- Per-trade risk (0.75% of balance)
- Max drawdown limit (15%)
- Max trades per session (3)
- Correlation limits
- Daily loss limits
- Position sizing (lot/quantity calculation)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from config.settings import RiskConfig
from core.logger import get_logger
from core.models import AccountState, Direction, Trade, TradeSignal, TradeStatus

logger = get_logger("risk.manager")


class RiskManager:
    def __init__(self, config: RiskConfig):
        self.config = config
        self.account = AccountState(
            balance=config.account_balance,
            equity=config.account_balance,
            peak_balance=config.account_balance,
        )
        self.open_trades: List[Trade] = []
        self.daily_trades: List[Trade] = []
        self._last_reset: datetime = datetime.utcnow()

    def can_trade(self) -> tuple[bool, str]:
        """Check all risk conditions before allowing a new trade."""
        self._maybe_reset_daily()

        if self.account.current_drawdown >= self.config.max_drawdown:
            msg = f"Max drawdown reached: {self.account.current_drawdown:.2%} >= {self.config.max_drawdown:.2%}"
            logger.warning(msg)
            return False, msg

        if self.account.session_trades >= self.config.max_trades_per_session:
            msg = f"Max session trades reached: {self.account.session_trades}/{self.config.max_trades_per_session}"
            logger.warning(msg)
            return False, msg

        daily_loss_pct = abs(self.account.daily_pnl) / self.account.balance if self.account.daily_pnl < 0 else 0
        if daily_loss_pct >= self.config.max_daily_loss:
            msg = f"Max daily loss reached: {daily_loss_pct:.2%}"
            logger.warning(msg)
            return False, msg

        if len(self.open_trades) >= self.config.max_trades_per_session:
            msg = f"Max concurrent trades: {len(self.open_trades)}"
            return False, msg

        return True, "OK"

    def calculate_position_size(
        self, signal: TradeSignal, symbol_info: Optional[dict] = None
    ) -> float:
        """
        Calculate position size based on risk amount and stop distance.
        Returns lot size for forex or quantity for crypto.
        """
        risk_amount = self.account.balance * self.config.risk_per_trade
        stop_distance = abs(signal.entry_price - signal.stop_loss)

        if stop_distance == 0:
            logger.error("Stop distance is zero — cannot size position")
            return 0.0

        if symbol_info:
            point = symbol_info.get("point", 0.00001)
            contract_size = symbol_info.get("trade_contract_size", 100000)
            stop_points = stop_distance / point
            if stop_points == 0:
                return 0.0
            lot_size = risk_amount / (stop_points * point * contract_size)

            vol_min = symbol_info.get("volume_min", 0.01)
            vol_max = symbol_info.get("volume_max", 100.0)
            vol_step = symbol_info.get("volume_step", 0.01)

            lot_size = max(vol_min, min(lot_size, vol_max))
            lot_size = round(lot_size / vol_step) * vol_step
            return round(lot_size, 2)
        else:
            position_size = risk_amount / stop_distance
            return round(position_size, 6)

    def validate_signal(self, signal: TradeSignal) -> tuple[bool, str]:
        """Validate a trade signal against risk rules."""
        can, reason = self.can_trade()
        if not can:
            return False, reason

        if signal.risk_reward < 1.0:
            return False, f"Risk:reward too low: {signal.risk_reward:.2f}"

        if self._is_correlated(signal.symbol):
            return False, f"Too many correlated trades for {signal.symbol}"

        if signal.stop_loss == 0 or signal.entry_price == 0:
            return False, "Invalid SL or entry price"

        return True, "OK"

    def register_trade(self, trade: Trade):
        """Register a new open trade."""
        self.open_trades.append(trade)
        self.account.open_trades = len(self.open_trades)
        self.account.session_trades += 1
        self.account.daily_trades += 1
        self.account.total_trades += 1
        logger.info(
            f"Trade registered: {trade.trade_id} {trade.symbol} "
            f"Session trades: {self.account.session_trades}"
        )

    def close_trade(self, trade: Trade, pnl: float):
        """Close a trade and update account state."""
        trade.status = TradeStatus.CLOSED
        trade.pnl = pnl
        trade.closed_at = datetime.utcnow()

        self.account.balance += pnl
        self.account.equity = self.account.balance
        self.account.daily_pnl += pnl

        if pnl > 0:
            self.account.winning_trades += 1
        else:
            self.account.losing_trades += 1

        if self.account.balance > self.account.peak_balance:
            self.account.peak_balance = self.account.balance

        dd = self.account.current_drawdown
        if dd > self.account.max_drawdown_reached:
            self.account.max_drawdown_reached = dd

        self.open_trades = [t for t in self.open_trades if t.trade_id != trade.trade_id]
        self.account.open_trades = len(self.open_trades)

        logger.info(
            f"Trade closed: {trade.trade_id} PnL={pnl:.2f} "
            f"Balance={self.account.balance:.2f} DD={dd:.2%}"
        )

    def update_equity(self, unrealized_pnl: float):
        """Update equity with unrealized P&L."""
        self.account.equity = self.account.balance + unrealized_pnl

    def _is_correlated(self, symbol: str) -> bool:
        base = symbol[:3] if len(symbol) >= 6 else symbol
        count = sum(1 for t in self.open_trades if t.symbol.startswith(base))
        return count >= self.config.max_correlated_trades

    def _maybe_reset_daily(self):
        now = datetime.utcnow()
        if now.date() > self._last_reset.date():
            self.account.daily_pnl = 0.0
            self.account.daily_trades = 0
            self.account.session_trades = 0
            self._last_reset = now
            logger.info("Daily risk counters reset")

    def get_risk_summary(self) -> dict:
        return {
            "balance": self.account.balance,
            "equity": self.account.equity,
            "drawdown": f"{self.account.current_drawdown:.2%}",
            "max_drawdown": f"{self.account.max_drawdown_reached:.2%}",
            "open_trades": self.account.open_trades,
            "session_trades": self.account.session_trades,
            "daily_pnl": self.account.daily_pnl,
            "win_rate": f"{self.account.win_rate:.2%}",
            "total_trades": self.account.total_trades,
        }
