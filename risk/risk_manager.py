from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import pandas as pd

from config.settings import settings
from core.models import (
    AccountState,
    Direction,
    Market,
    MultiTimeframeAnalysis,
    OpenTrade,
    TradeSignal,
    Session,
)
from utils.helpers import (
    calculate_crypto_quantity,
    calculate_lot_size,
    ewm_atr,
    find_swing_highs,
    find_swing_lows,
    price_to_pips,
    round_price,
)
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RiskCheckResult:
    allowed: bool
    reason: str = ""
    risk_amount: float = 0.0
    lot_size: float = 0.0
    stop_loss: float = 0.0
    tp1: float = 0.0
    tp2: float = 0.0
    tp3: float = 0.0
    risk_reward: float = 0.0
    atr_value: float = 0.0


class RiskManager:
    """
    Centralised risk management for all trade decisions.

    Responsibilities:
    - Position sizing (fixed fractional, ATR-based)
    - Stop-loss calculation (ATR or structure-based)
    - Multi-TP calculation (1R / 1.5R / 2R)
    - Pre-trade filters: drawdown, session trade limit
    - Break-even management
    - Drawdown monitoring
    """

    def __init__(self) -> None:
        self._s = settings

    # ------------------------------------------------------------------
    # Pre-trade validation
    # ------------------------------------------------------------------

    def validate_trade(
        self,
        symbol: str,
        market: Market,
        direction: Direction,
        df: pd.DataFrame,
        account: AccountState,
        mta: MultiTimeframeAnalysis,
    ) -> RiskCheckResult:
        """
        Full pre-trade risk check. Returns a RiskCheckResult with all
        calculated parameters if the trade is approved.
        """
        # ── Drawdown guard ─────────────────────────────────────────────
        account.update_drawdown()
        if account.max_drawdown_breached:
            return RiskCheckResult(
                allowed=False,
                reason=f"Max drawdown breached: {account.drawdown_pct:.1%} >= {self._s.max_drawdown:.1%}",
            )

        # ── Session trade limit ────────────────────────────────────────
        if account.session_limit_reached:
            return RiskCheckResult(
                allowed=False,
                reason=f"Session trade limit reached: {account.session_trades}/{self._s.max_trades_per_session}",
            )

        # ── Duplicate symbol check ────────────────────────────────────
        open_symbols = {t.symbol for t in account.open_trades if t.status.value == "open"}
        if symbol in open_symbols:
            return RiskCheckResult(
                allowed=False,
                reason=f"Already have open trade on {symbol}",
            )

        # ── Calculate ATR and SL ──────────────────────────────────────
        atr = self._get_atr(df)
        if atr <= 0:
            return RiskCheckResult(allowed=False, reason="ATR calculation failed")

        entry_price = float(df["close"].iloc[-1])

        # ATR-based SL (primary)
        sl_atr = self._calculate_atr_stop(entry_price, direction, atr)

        # Structure SL (secondary — use whichever is further)
        sl_struct = self._calculate_structure_stop(df, direction, entry_price)

        # Use the wider stop to avoid premature stopouts
        if direction == Direction.LONG:
            stop_loss = min(sl_atr, sl_struct) if sl_struct > 0 else sl_atr
        else:
            stop_loss = max(sl_atr, sl_struct) if sl_struct > 0 else sl_atr

        stop_loss = round_price(stop_loss)

        sl_distance = abs(entry_price - stop_loss)
        if sl_distance <= 0:
            return RiskCheckResult(allowed=False, reason="Invalid SL distance")

        # ── Risk/Reward validation ────────────────────────────────────
        tp1, tp2, tp3 = self._calculate_take_profits(
            entry_price, direction, sl_distance
        )
        rr = (tp2 - entry_price) / sl_distance if direction == Direction.LONG else (entry_price - tp2) / sl_distance
        if rr < self._s.min_rr_ratio:
            return RiskCheckResult(
                allowed=False,
                reason=f"R:R too low: {rr:.2f} < {self._s.min_rr_ratio:.1f}",
            )

        # ── Position sizing ───────────────────────────────────────────
        risk_amount = account.balance * self._s.risk_per_trade

        if market == Market.FOREX:
            pip_size = 0.01 if "JPY" in symbol.upper() else 0.0001
            sl_pips = price_to_pips(sl_distance, symbol)
            lot_size = calculate_lot_size(
                account_balance=account.balance,
                risk_pct=self._s.risk_per_trade,
                stop_loss_pips=sl_pips,
                pip_value_per_lot=10.0,
            )
        else:
            lot_size = calculate_crypto_quantity(
                account_balance=account.balance,
                risk_pct=self._s.risk_per_trade,
                entry_price=entry_price,
                stop_loss_price=stop_loss,
            )

        logger.info(
            "Risk check OK | %s %s | entry=%.5f SL=%.5f TP1=%.5f TP2=%.5f TP3=%.5f | lot=%.4f RR=%.2f",
            direction.value.upper(),
            symbol,
            entry_price,
            stop_loss,
            tp1,
            tp2,
            tp3,
            lot_size,
            rr,
        )

        return RiskCheckResult(
            allowed=True,
            risk_amount=risk_amount,
            lot_size=lot_size,
            stop_loss=stop_loss,
            tp1=tp1,
            tp2=tp2,
            tp3=tp3,
            risk_reward=rr,
            atr_value=atr,
        )

    # ------------------------------------------------------------------
    # Trade lifecycle management
    # ------------------------------------------------------------------

    def should_move_to_breakeven(self, trade: OpenTrade, current_price: float) -> bool:
        """Move SL to entry price after TP1 is hit."""
        if trade.breakeven_moved or not trade.tp1_hit:
            return False
        return True

    def check_tp_levels(
        self, trade: OpenTrade, current_price: float
    ) -> Tuple[bool, bool, bool]:
        """Returns (tp1_hit, tp2_hit, tp3_hit) booleans based on current price."""
        if trade.direction == Direction.LONG:
            tp1 = current_price >= trade.tp1 and not trade.tp1_hit
            tp2 = current_price >= trade.tp2 and not trade.tp2_hit
            tp3 = current_price >= trade.tp3 and not trade.tp3_hit
        else:
            tp1 = current_price <= trade.tp1 and not trade.tp1_hit
            tp2 = current_price <= trade.tp2 and not trade.tp2_hit
            tp3 = current_price <= trade.tp3 and not trade.tp3_hit
        return tp1, tp2, tp3

    def is_stopped_out(self, trade: OpenTrade, current_price: float) -> bool:
        if trade.direction == Direction.LONG:
            return current_price <= trade.stop_loss
        return current_price >= trade.stop_loss

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_atr(self, df: pd.DataFrame) -> float:
        try:
            atr_series = ewm_atr(df, self._s.atr_period)
            return float(atr_series.iloc[-1])
        except Exception:
            return 0.0

    def _calculate_atr_stop(
        self, entry: float, direction: Direction, atr: float
    ) -> float:
        offset = atr * self._s.atr_sl_multiplier
        if direction == Direction.LONG:
            return entry - offset
        return entry + offset

    def _calculate_structure_stop(
        self,
        df: pd.DataFrame,
        direction: Direction,
        entry: float,
        lookback: int = 10,
    ) -> float:
        try:
            recent = df.iloc[-lookback:]
            if direction == Direction.LONG:
                # Place SL below the most recent swing low
                return float(recent["low"].min()) * 0.9999
            else:
                return float(recent["high"].max()) * 1.0001
        except Exception:
            return 0.0

    def _calculate_take_profits(
        self,
        entry: float,
        direction: Direction,
        sl_distance: float,
    ) -> Tuple[float, float, float]:
        if direction == Direction.LONG:
            tp1 = entry + sl_distance * self._s.tp1_ratio
            tp2 = entry + sl_distance * self._s.tp2_ratio
            tp3 = entry + sl_distance * self._s.tp3_ratio
        else:
            tp1 = entry - sl_distance * self._s.tp1_ratio
            tp2 = entry - sl_distance * self._s.tp2_ratio
            tp3 = entry - sl_distance * self._s.tp3_ratio
        return (
            round_price(tp1),
            round_price(tp2),
            round_price(tp3),
        )


# Module-level singleton
risk_manager = RiskManager()
