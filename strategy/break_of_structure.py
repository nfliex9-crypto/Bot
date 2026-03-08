from __future__ import annotations

from typing import List, Optional, Tuple

import pandas as pd

from config.settings import settings
from core.models import (
    BOSSignal,
    Direction,
    MarketBias,
    SwingPoint,
    TrendStructure,
)
from utils.helpers import find_swing_highs, find_swing_lows
from utils.logger import get_logger

logger = get_logger(__name__)


def _build_swing_list(df: pd.DataFrame, lookback: int) -> List[SwingPoint]:
    """Build an ordered list of alternating swing highs and lows."""
    high_mask = find_swing_highs(df["high"], lookback=lookback)
    low_mask = find_swing_lows(df["low"], lookback=lookback)

    points: List[SwingPoint] = []
    for i in df.index:
        iloc = df.index.get_loc(i)
        if high_mask.loc[i]:
            points.append(
                SwingPoint(
                    price=df.loc[i, "high"],
                    index=iloc,
                    timestamp=i,
                    is_high=True,
                )
            )
        elif low_mask.loc[i]:
            points.append(
                SwingPoint(
                    price=df.loc[i, "low"],
                    index=iloc,
                    timestamp=i,
                    is_high=False,
                )
            )

    return sorted(points, key=lambda p: p.index)


def _determine_market_bias(swings: List[SwingPoint]) -> MarketBias:
    """
    Assess market bias from the last N swing points.
    - Bullish  = higher highs + higher lows
    - Bearish  = lower highs + lower lows
    - Neutral  = mixed
    """
    if len(swings) < 4:
        return MarketBias.NEUTRAL

    recent = swings[-6:]
    highs = [s for s in recent if s.is_high]
    lows = [s for s in recent if not s.is_high]

    if len(highs) < 2 or len(lows) < 2:
        return MarketBias.NEUTRAL

    hh = highs[-1].price > highs[-2].price
    hl = lows[-1].price > lows[-2].price
    ll = lows[-1].price < lows[-2].price
    lh = highs[-1].price < highs[-2].price

    if hh and hl:
        return MarketBias.BULLISH
    if ll and lh:
        return MarketBias.BEARISH
    return MarketBias.NEUTRAL


def _determine_trend_structure(swings: List[SwingPoint]) -> TrendStructure:
    if len(swings) < 4:
        return TrendStructure.RANGING

    recent = swings[-4:]
    highs = [s for s in recent if s.is_high]
    lows = [s for s in recent if not s.is_high]

    if len(highs) < 2 or len(lows) < 2:
        return TrendStructure.RANGING

    hh = highs[-1].price > highs[-2].price
    hl = lows[-1].price > lows[-2].price
    ll = lows[-1].price < lows[-2].price
    lh = highs[-1].price < highs[-2].price

    if hh and hl:
        return TrendStructure.UPTREND
    if ll and lh:
        return TrendStructure.DOWNTREND
    return TrendStructure.RANGING


class BreakOfStructureDetector:
    """
    Detects Break of Structure (BOS) signals.

    A bullish BOS occurs when price closes above the most recent significant
    swing high (after a bearish sweep), signalling a potential reversal to
    the upside.

    A bearish BOS occurs when price closes below the most recent significant
    swing low, signalling a potential reversal to the downside.
    """

    def __init__(self) -> None:
        self._lookback = settings.swing_lookback
        self._confirm_bars = settings.bos_confirmation_bars

    # ------------------------------------------------------------------
    def detect(
        self, df: pd.DataFrame, symbol: str
    ) -> Optional[BOSSignal]:
        if len(df) < self._lookback * 2 + 5:
            return None

        swings = _build_swing_list(df.iloc[:-1], self._lookback)
        if not swings:
            return None

        last_close = df.iloc[-1]["close"]
        last_ts = df.index[-1]

        # ── Bullish BOS ───────────────────────────────────────────────
        recent_highs = [s for s in swings if s.is_high]
        if recent_highs:
            last_high = recent_highs[-1]
            if last_close > last_high.price:
                sig = BOSSignal(
                    symbol=symbol,
                    direction=Direction.LONG,
                    break_price=last_close,
                    previous_swing=last_high.price,
                    timestamp=last_ts,
                    confirmed=True,
                    bars_confirmed=self._count_confirmation_bars(
                        df, last_high.price, Direction.LONG
                    ),
                )
                logger.debug(
                    "BOS LONG detected on %s: close %.5f > swing_high %.5f",
                    symbol, last_close, last_high.price,
                )
                return sig

        # ── Bearish BOS ───────────────────────────────────────────────
        recent_lows = [s for s in swings if not s.is_high]
        if recent_lows:
            last_low = recent_lows[-1]
            if last_close < last_low.price:
                sig = BOSSignal(
                    symbol=symbol,
                    direction=Direction.SHORT,
                    break_price=last_close,
                    previous_swing=last_low.price,
                    timestamp=last_ts,
                    confirmed=True,
                    bars_confirmed=self._count_confirmation_bars(
                        df, last_low.price, Direction.SHORT
                    ),
                )
                logger.debug(
                    "BOS SHORT detected on %s: close %.5f < swing_low %.5f",
                    symbol, last_close, last_low.price,
                )
                return sig

        return None

    # ------------------------------------------------------------------
    def market_bias(self, df: pd.DataFrame) -> MarketBias:
        if len(df) < self._lookback * 2:
            return MarketBias.NEUTRAL
        swings = _build_swing_list(df, self._lookback)
        return _determine_market_bias(swings)

    def trend_structure(self, df: pd.DataFrame) -> TrendStructure:
        if len(df) < self._lookback * 2:
            return TrendStructure.RANGING
        swings = _build_swing_list(df, self._lookback)
        return _determine_trend_structure(swings)

    # ------------------------------------------------------------------
    def _count_confirmation_bars(
        self, df: pd.DataFrame, level: float, direction: Direction
    ) -> int:
        """Count consecutive bars that remain on the correct side of the level."""
        count = 0
        for candle in reversed(df.iloc[-self._confirm_bars - 3:].to_dict("records")):
            if direction == Direction.LONG and candle["close"] > level:
                count += 1
            elif direction == Direction.SHORT and candle["close"] < level:
                count += 1
            else:
                break
        return count
