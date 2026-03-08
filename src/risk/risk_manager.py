"""
Risk Management System.

Handles:
- Position sizing (ATR-based)
- Max drawdown enforcement
- Max trades per session
- Account health monitoring
- Lot size calculation for forex and crypto
"""

from dataclasses import dataclass
from typing import Optional, Tuple
from decimal import Decimal
import math
from loguru import logger

from config.settings import settings


@dataclass
class PositionSize:
    lot_size: float
    risk_amount: float
    risk_pct: float
    stop_distance: float
    pip_value: float
    valid: bool
    rejection_reason: Optional[str] = None


@dataclass
class RiskCheck:
    approved: bool
    rejection_reason: Optional[str]
    current_drawdown_pct: float
    trades_this_session: int
    remaining_risk_budget: float


class RiskManager:
    """
    Central risk management engine.
    All position sizing flows through this class.
    """

    def __init__(self):
        self._session_trades: int = 0
        self._session_pnl: float = 0.0
        self._peak_balance: float = settings.account_balance
        self._current_balance: float = settings.account_balance
        self._open_risk: float = 0.0    # Sum of risk on currently open trades

    # ── Public API ────────────────────────────────────────────────────────────

    def update_balance(self, balance: float) -> None:
        self._current_balance = balance
        if balance > self._peak_balance:
            self._peak_balance = balance

    def record_trade_open(self, risk_amount: float) -> None:
        self._session_trades += 1
        self._open_risk += risk_amount

    def record_trade_close(self, risk_amount: float, pnl: float) -> None:
        self._open_risk = max(0.0, self._open_risk - risk_amount)
        self._session_pnl += pnl
        self._current_balance += pnl

    def reset_session(self) -> None:
        self._session_trades = 0
        self._session_pnl = 0.0

    @property
    def current_drawdown_pct(self) -> float:
        if self._peak_balance == 0:
            return 0.0
        return round((self._peak_balance - self._current_balance) / self._peak_balance, 6)

    @property
    def session_trades(self) -> int:
        return self._session_trades

    # ── Risk Pre-Check ────────────────────────────────────────────────────────

    def pre_trade_check(self) -> RiskCheck:
        """
        Run all risk checks before allowing a new trade.
        Returns RiskCheck with approved=True if all checks pass.
        """
        drawdown = self.current_drawdown_pct

        # Max drawdown check
        if drawdown >= settings.max_drawdown_pct:
            return RiskCheck(
                approved=False,
                rejection_reason=f"Max drawdown reached: {drawdown:.2%} ≥ {settings.max_drawdown_pct:.2%}",
                current_drawdown_pct=drawdown,
                trades_this_session=self._session_trades,
                remaining_risk_budget=0.0,
            )

        # Max trades per session
        if self._session_trades >= settings.max_trades_per_session:
            return RiskCheck(
                approved=False,
                rejection_reason=f"Max trades per session reached: {self._session_trades}",
                current_drawdown_pct=drawdown,
                trades_this_session=self._session_trades,
                remaining_risk_budget=0.0,
            )

        remaining_drawdown = settings.max_drawdown_pct - drawdown
        risk_budget = self._current_balance * remaining_drawdown

        return RiskCheck(
            approved=True,
            rejection_reason=None,
            current_drawdown_pct=drawdown,
            trades_this_session=self._session_trades,
            remaining_risk_budget=risk_budget,
        )

    # ── Position Sizing ───────────────────────────────────────────────────────

    def calculate_position_size_forex(
        self,
        symbol: str,
        entry: float,
        stop_loss: float,
        account_currency: str = "USD",
        contract_size: float = 100000,
        pip_value_per_lot: Optional[float] = None,
    ) -> PositionSize:
        """
        Calculate forex lot size based on risk percentage.

        risk_amount = balance × risk_pct
        pip_risk = |entry - stop_loss| / pip_size
        lot_size = risk_amount / (pip_risk × pip_value_per_lot)
        """
        risk_amount = self._current_balance * settings.risk_per_trade
        stop_distance = abs(entry - stop_loss)

        if stop_distance == 0:
            return PositionSize(
                lot_size=0.0, risk_amount=0.0, risk_pct=0.0,
                stop_distance=0.0, pip_value=0.0, valid=False,
                rejection_reason="Stop distance is zero",
            )

        # Determine pip size based on symbol
        pip_size = 0.0001 if "JPY" not in symbol else 0.01
        pip_risk = stop_distance / pip_size

        # pip_value_per_lot: default USD-quoted pairs
        if pip_value_per_lot is None:
            if symbol.endswith("USD"):
                pip_value_per_lot = pip_size * contract_size
            elif symbol.startswith("USD"):
                # e.g. USDJPY: pip value = (pip_size / current price) * contract_size
                pip_value_per_lot = (pip_size / entry) * contract_size
            else:
                # Cross pairs: approximate
                pip_value_per_lot = pip_size * contract_size

        if pip_value_per_lot == 0:
            return PositionSize(
                lot_size=0.0, risk_amount=0.0, risk_pct=0.0,
                stop_distance=stop_distance, pip_value=0.0, valid=False,
                rejection_reason="Cannot determine pip value",
            )

        raw_lots = risk_amount / (pip_risk * pip_value_per_lot)

        # Round down to broker minimum step (0.01 lot standard)
        lot_size = math.floor(raw_lots * 100) / 100
        lot_size = max(lot_size, 0.01)

        return PositionSize(
            lot_size=lot_size,
            risk_amount=risk_amount,
            risk_pct=settings.risk_per_trade,
            stop_distance=stop_distance,
            pip_value=pip_value_per_lot,
            valid=True,
        )

    def calculate_position_size_crypto(
        self,
        symbol: str,
        entry: float,
        stop_loss: float,
        min_qty: float = 0.001,
        step_size: float = 0.001,
    ) -> PositionSize:
        """
        Calculate crypto quantity based on risk percentage.

        risk_amount = balance × risk_pct
        stop_distance = |entry - stop_loss|
        quantity = risk_amount / stop_distance
        """
        risk_amount = self._current_balance * settings.risk_per_trade
        stop_distance = abs(entry - stop_loss)

        if stop_distance == 0:
            return PositionSize(
                lot_size=0.0, risk_amount=0.0, risk_pct=0.0,
                stop_distance=0.0, pip_value=0.0, valid=False,
                rejection_reason="Stop distance is zero",
            )

        raw_qty = risk_amount / stop_distance

        # Round to step size
        qty = math.floor(raw_qty / step_size) * step_size
        qty = max(qty, min_qty)

        # Validate minimum notional
        notional = qty * entry
        if notional < 10.0:
            return PositionSize(
                lot_size=qty, risk_amount=risk_amount, risk_pct=settings.risk_per_trade,
                stop_distance=stop_distance, pip_value=0.0, valid=False,
                rejection_reason=f"Order notional too small: ${notional:.2f} < $10",
            )

        return PositionSize(
            lot_size=round(qty, 8),
            risk_amount=risk_amount,
            risk_pct=settings.risk_per_trade,
            stop_distance=stop_distance,
            pip_value=0.0,
            valid=True,
        )

    # ── Take-Profit Levels ────────────────────────────────────────────────────

    @staticmethod
    def calculate_take_profits(
        entry: float, stop_loss: float, direction: str
    ) -> Tuple[float, float, float]:
        """Return (tp1, tp2, tp3) based on configured R-multiples."""
        risk = abs(entry - stop_loss)
        if direction == "bullish":
            tp1 = entry + risk * settings.tp1_r
            tp2 = entry + risk * settings.tp2_r
            tp3 = entry + risk * settings.tp3_r
        else:
            tp1 = entry - risk * settings.tp1_r
            tp2 = entry - risk * settings.tp2_r
            tp3 = entry - risk * settings.tp3_r
        return round(tp1, 8), round(tp2, 8), round(tp3, 8)

    @staticmethod
    def calculate_break_even(entry: float, tp1: float, direction: str) -> float:
        """
        Break-even price: move stop to entry after TP1 is hit.
        Add a small buffer to cover spread.
        buffer = 10% of (tp1 - entry) distance.
        """
        buffer = abs(tp1 - entry) * 0.1
        if direction == "bullish":
            return round(entry + buffer, 8)
        return round(entry - buffer, 8)

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        return {
            "current_balance": self._current_balance,
            "peak_balance": self._peak_balance,
            "current_drawdown_pct": self.current_drawdown_pct,
            "session_trades": self._session_trades,
            "session_pnl": self._session_pnl,
            "open_risk": self._open_risk,
            "max_drawdown_pct": settings.max_drawdown_pct,
            "max_trades_per_session": settings.max_trades_per_session,
            "risk_per_trade": settings.risk_per_trade,
        }
