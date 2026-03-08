"""
Risk Manager

Enforces risk rules: max drawdown, session trade limits, position sizing,
break-even management after TP1, and partial close logic for TP levels.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.core.config import get_settings
from app.core.logging import get_logger
from app.risk_engine.position_sizer import PositionSizer, PositionSize
from app.strategy.pullback_entry import TradeSetup

logger = get_logger(__name__)


@dataclass
class RiskAssessment:
    approved: bool
    position_size: Optional[PositionSize] = None
    rejection_reason: Optional[str] = None
    current_drawdown: float = 0.0
    session_trades: int = 0
    risk_score: float = 0.0


@dataclass
class ActiveTradeRisk:
    order_id: str
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    lot_size: float
    tp1_hit: bool = False
    tp2_hit: bool = False
    break_even_set: bool = False
    partial_close_1: bool = False
    partial_close_2: bool = False


class RiskManager:
    """Manages all risk parameters and enforces trading rules."""

    def __init__(self):
        self.settings = get_settings()
        self.position_sizer = PositionSizer()
        self.active_trades: dict[str, ActiveTradeRisk] = {}
        self.session_trades: int = 0
        self.session_start: datetime = datetime.now(timezone.utc)
        self.peak_equity: float = 0.0
        self.initial_equity: float = 0.0

    def initialize(self, account_equity: float) -> None:
        self.initial_equity = account_equity
        self.peak_equity = account_equity
        logger.info("Risk manager initialized", equity=account_equity)

    def assess_trade(
        self,
        setup: TradeSetup,
        account_equity: float,
        market_type: str = "forex",
    ) -> RiskAssessment:
        """Evaluate whether a trade setup passes all risk checks."""
        self.peak_equity = max(self.peak_equity, account_equity)

        drawdown = self._calculate_drawdown(account_equity)
        if drawdown >= self.settings.max_drawdown:
            logger.warning(
                "Trade rejected: max drawdown exceeded",
                drawdown=round(drawdown * 100, 2),
                max_allowed=round(self.settings.max_drawdown * 100, 2),
            )
            return RiskAssessment(
                approved=False,
                rejection_reason=f"Max drawdown {drawdown:.1%} exceeds limit {self.settings.max_drawdown:.1%}",
                current_drawdown=drawdown,
                session_trades=self.session_trades,
            )

        if self.session_trades >= self.settings.max_trades_per_session:
            logger.warning("Trade rejected: session limit reached", trades=self.session_trades)
            return RiskAssessment(
                approved=False,
                rejection_reason=f"Session limit reached ({self.session_trades}/{self.settings.max_trades_per_session})",
                current_drawdown=drawdown,
                session_trades=self.session_trades,
            )

        if setup.confidence < 0.4:
            logger.warning("Trade rejected: low confidence", confidence=setup.confidence)
            return RiskAssessment(
                approved=False,
                rejection_reason=f"Confidence too low ({setup.confidence:.1%})",
                current_drawdown=drawdown,
                session_trades=self.session_trades,
            )

        if market_type == "forex":
            position = self.position_sizer.calculate_forex_position(
                account_equity, setup.entry_price, setup.stop_loss, setup.symbol
            )
        else:
            position = self.position_sizer.calculate_crypto_position(
                account_equity, setup.entry_price, setup.stop_loss, setup.symbol
            )

        if position.lot_size == 0:
            return RiskAssessment(
                approved=False,
                rejection_reason="Position size calculation failed",
                current_drawdown=drawdown,
                session_trades=self.session_trades,
            )

        total_exposure = self._calculate_total_exposure(account_equity)
        if total_exposure + position.risk_percent > self.settings.risk_per_trade * 5:
            return RiskAssessment(
                approved=False,
                rejection_reason="Total exposure too high",
                current_drawdown=drawdown,
                session_trades=self.session_trades,
            )

        risk_score = self._calculate_risk_score(setup, drawdown, position)

        logger.info(
            "Trade approved",
            symbol=setup.symbol, direction=setup.direction,
            lots=position.lot_size, risk_score=round(risk_score, 2),
        )

        return RiskAssessment(
            approved=True,
            position_size=position,
            current_drawdown=drawdown,
            session_trades=self.session_trades,
            risk_score=risk_score,
        )

    def register_trade(self, trade: ActiveTradeRisk) -> None:
        """Register a new active trade for monitoring."""
        self.active_trades[trade.order_id] = trade
        self.session_trades += 1
        logger.info("Trade registered", order_id=trade.order_id, symbol=trade.symbol)

    def check_tp_levels(self, order_id: str, current_price: float) -> dict:
        """Check if any TP levels have been hit and return required actions."""
        trade = self.active_trades.get(order_id)
        if not trade:
            return {}

        actions = {}

        if trade.direction == "long":
            if not trade.tp1_hit and current_price >= trade.take_profit_1:
                trade.tp1_hit = True
                actions["tp1_hit"] = True
                actions["close_partial_1"] = True
                actions["partial_volume_1"] = trade.lot_size * 0.33
                actions["move_to_breakeven"] = True
                actions["new_stop_loss"] = trade.entry_price
                logger.info("TP1 hit - moving to break-even", order_id=order_id)

            if not trade.tp2_hit and current_price >= trade.take_profit_2:
                trade.tp2_hit = True
                actions["tp2_hit"] = True
                actions["close_partial_2"] = True
                actions["partial_volume_2"] = trade.lot_size * 0.33
                actions["trail_stop"] = True
                actions["new_stop_loss"] = trade.take_profit_1
                logger.info("TP2 hit - trailing stop", order_id=order_id)

            if current_price >= trade.take_profit_3:
                actions["tp3_hit"] = True
                actions["close_remaining"] = True
                logger.info("TP3 hit - closing remaining", order_id=order_id)

        elif trade.direction == "short":
            if not trade.tp1_hit and current_price <= trade.take_profit_1:
                trade.tp1_hit = True
                actions["tp1_hit"] = True
                actions["close_partial_1"] = True
                actions["partial_volume_1"] = trade.lot_size * 0.33
                actions["move_to_breakeven"] = True
                actions["new_stop_loss"] = trade.entry_price
                logger.info("TP1 hit - moving to break-even", order_id=order_id)

            if not trade.tp2_hit and current_price <= trade.take_profit_2:
                trade.tp2_hit = True
                actions["tp2_hit"] = True
                actions["close_partial_2"] = True
                actions["partial_volume_2"] = trade.lot_size * 0.33
                actions["trail_stop"] = True
                actions["new_stop_loss"] = trade.take_profit_1
                logger.info("TP2 hit - trailing stop", order_id=order_id)

            if current_price <= trade.take_profit_3:
                actions["tp3_hit"] = True
                actions["close_remaining"] = True
                logger.info("TP3 hit - closing remaining", order_id=order_id)

        return actions

    def remove_trade(self, order_id: str) -> None:
        if order_id in self.active_trades:
            del self.active_trades[order_id]
            logger.info("Trade removed from risk manager", order_id=order_id)

    def reset_session(self) -> None:
        self.session_trades = 0
        self.session_start = datetime.now(timezone.utc)
        logger.info("Trading session reset")

    def _calculate_drawdown(self, current_equity: float) -> float:
        if self.peak_equity == 0:
            return 0.0
        return (self.peak_equity - current_equity) / self.peak_equity

    def _calculate_total_exposure(self, account_equity: float) -> float:
        total = 0.0
        for trade in self.active_trades.values():
            risk = abs(trade.entry_price - trade.stop_loss) * trade.lot_size
            total += risk / account_equity if account_equity > 0 else 0
        return total

    def _calculate_risk_score(
        self, setup: TradeSetup, drawdown: float, position: PositionSize
    ) -> float:
        """Higher score = higher risk. Scale 0-10."""
        score = 0.0
        score += (1.0 - setup.confidence) * 3.0
        score += drawdown * 10.0
        score += position.risk_percent * 100.0
        score += len(self.active_trades) * 0.5
        score += (self.session_trades / max(1, self.settings.max_trades_per_session)) * 2.0
        return min(10.0, score)

    def get_status(self, current_equity: float) -> dict:
        drawdown = self._calculate_drawdown(current_equity)
        return {
            "active_trades": len(self.active_trades),
            "session_trades": self.session_trades,
            "max_trades_per_session": self.settings.max_trades_per_session,
            "current_drawdown": round(drawdown * 100, 2),
            "max_drawdown": round(self.settings.max_drawdown * 100, 2),
            "peak_equity": round(self.peak_equity, 2),
            "current_equity": round(current_equity, 2),
            "risk_per_trade": round(self.settings.risk_per_trade * 100, 2),
            "can_trade": (
                drawdown < self.settings.max_drawdown
                and self.session_trades < self.settings.max_trades_per_session
            ),
        }
