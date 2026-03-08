from __future__ import annotations

from typing import Optional

import pandas as pd

from config.settings import settings
from core.models import BOSSignal, Direction, PullbackSignal, SwingPoint
from utils.helpers import ewm_atr, fib_retracement_levels, find_swing_highs, find_swing_lows
from utils.logger import get_logger

logger = get_logger(__name__)


def _find_order_block(
    df: pd.DataFrame,
    direction: Direction,
    lookback: int = 10,
) -> Optional[float]:
    """
    Identify the last bearish candle before a bullish BOS (for longs),
    or the last bullish candle before a bearish BOS (for shorts).
    This is the order block / institutional candle.
    """
    recent = df.iloc[-lookback:]
    if direction == Direction.LONG:
        # Last bearish candle (close < open)
        bearish = recent[recent["close"] < recent["open"]]
        if not bearish.empty:
            return float((bearish.iloc[-1]["open"] + bearish.iloc[-1]["close"]) / 2)
    else:
        # Last bullish candle (close > open)
        bullish = recent[recent["close"] > recent["open"]]
        if not bullish.empty:
            return float((bullish.iloc[-1]["open"] + bullish.iloc[-1]["close"]) / 2)
    return None


class PullbackEntryDetector:
    """
    Waits for a pullback into a Fibonacci retracement zone (38.2%–61.8%)
    after a Break of Structure, then provides an entry signal.

    Entry confirmation criteria:
    1. BOS has been detected in the direction of bias
    2. Price pulls back into the 0.382–0.618 fib zone
    3. A confirmation candle (engulfing / pin bar) forms in the zone
    4. Entry is placed at the close of the confirmation candle
    """

    def __init__(self) -> None:
        self._fib_min = settings.pullback_fib_min
        self._fib_max = settings.pullback_fib_max
        self._lookback = settings.swing_lookback

    # ------------------------------------------------------------------
    def detect(
        self,
        df: pd.DataFrame,
        symbol: str,
        bos_signal: Optional[BOSSignal] = None,
    ) -> Optional[PullbackSignal]:
        if len(df) < self._lookback * 2 + 5:
            return None

        if bos_signal is None or not bos_signal.confirmed:
            return None

        direction = bos_signal.direction

        # Identify the most recent swing range for Fibonacci
        swing_low, swing_high = self._get_last_swing_range(df, direction)
        if swing_low is None or swing_high is None:
            return None

        fib_levels = fib_retracement_levels(swing_low, swing_high, direction.value)
        fib_entry_min = fib_levels[f"{self._fib_min:.3f}"]
        fib_entry_max = fib_levels[f"{self._fib_max:.3f}"]

        last_candle = df.iloc[-1]
        current_price = last_candle["close"]

        if direction == Direction.LONG:
            in_fib_zone = fib_entry_max <= current_price <= fib_entry_min
        else:
            in_fib_zone = fib_entry_min <= current_price <= fib_entry_max

        if not in_fib_zone:
            return None

        # Confirm entry candle (momentum candle in direction)
        confirmed = self._confirm_entry_candle(last_candle, df.iloc[-2], direction)
        if not confirmed:
            return None

        order_block = _find_order_block(df, direction, lookback=10)

        sig = PullbackSignal(
            symbol=symbol,
            direction=direction,
            entry_price=current_price,
            fib_level=self._nearest_fib_label(current_price, fib_levels, direction),
            swing_low=swing_low,
            swing_high=swing_high,
            timestamp=df.index[-1],
            valid=True,
            order_block_price=order_block,
        )
        logger.debug(
            "Pullback %s entry on %s at %.5f (fib zone %.5f–%.5f)",
            direction.value, symbol, current_price, fib_entry_max, fib_entry_min,
        )
        return sig

    # ------------------------------------------------------------------
    def _get_last_swing_range(
        self,
        df: pd.DataFrame,
        direction: Direction,
    ):
        lookback = min(self._lookback * 2, len(df) - 1)
        recent = df.iloc[-lookback:]

        swing_high = float(recent["high"].max())
        swing_low = float(recent["low"].min())

        if swing_high <= swing_low:
            return None, None
        return swing_low, swing_high

    @staticmethod
    def _confirm_entry_candle(
        candle: pd.Series,
        prev_candle: pd.Series,
        direction: Direction,
    ) -> bool:
        body = abs(candle["close"] - candle["open"])
        candle_range = candle["high"] - candle["low"]
        if candle_range == 0:
            return False
        body_pct = body / candle_range

        if direction == Direction.LONG:
            bullish_close = candle["close"] > candle["open"]
            engulfing = candle["close"] > prev_candle["open"] and candle["open"] < prev_candle["close"]
            pin_bar = (
                (candle["close"] - candle["low"]) > candle_range * 0.6
                and body_pct < 0.35
            )
            return bullish_close and (body_pct > 0.5 or engulfing or pin_bar)

        # SHORT
        bearish_close = candle["close"] < candle["open"]
        engulfing = candle["close"] < prev_candle["open"] and candle["open"] > prev_candle["close"]
        pin_bar = (
            (candle["high"] - candle["close"]) > candle_range * 0.6
            and body_pct < 0.35
        )
        return bearish_close and (body_pct > 0.5 or engulfing or pin_bar)

    @staticmethod
    def _nearest_fib_label(
        price: float, fib_levels: dict, direction: Direction
    ) -> str:
        return min(fib_levels, key=lambda k: abs(fib_levels[k] - price))
