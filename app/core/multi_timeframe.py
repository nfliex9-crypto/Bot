"""Multi-timeframe analysis: H1 bias, M15 structure, M5 execution."""
import pandas as pd
import numpy as np
from datetime import datetime
from .models import MarketStructure, SwingPoint


def detect_swing_points(ohlcv: pd.DataFrame, lookback: int = 5) -> list[SwingPoint]:
    """Detect swing highs and lows using pivot points."""
    highs = ohlcv["high"].values
    lows = ohlcv["low"].values
    times = ohlcv.index.tolist() if isinstance(ohlcv.index, pd.DatetimeIndex) else ohlcv["time"].tolist()

    swings = []
    for i in range(lookback, len(ohlcv) - lookback):
        # Swing high
        if all(highs[i] >= highs[i - j] for j in range(1, lookback + 1)) and all(
            highs[i] >= highs[i + j] for j in range(1, lookback + 1)
        ):
            swings.append(
                SwingPoint(
                    price=float(highs[i]),
                    time=times[i] if isinstance(times[i], datetime) else pd.Timestamp(times[i]).to_pydatetime(),
                    is_high=True,
                    timeframe="",
                )
            )
        # Swing low
        if all(lows[i] <= lows[i - j] for j in range(1, lookback + 1)) and all(
            lows[i] <= lows[i + j] for j in range(1, lookback + 1)
        ):
            swings.append(
                SwingPoint(
                    price=float(lows[i]),
                    time=times[i] if isinstance(times[i], datetime) else pd.Timestamp(times[i]).to_pydatetime(),
                    is_high=False,
                    timeframe="",
                )
            )
    return swings


def build_market_structure(
    ohlcv: pd.DataFrame, timeframe: str, lookback: int = 20
) -> MarketStructure:
    """Build market structure from OHLCV data."""
    swings = detect_swing_points(ohlcv, lookback=lookback)
    swings = swings[-lookback:]  # Recent swings

    highs = [s for s in swings if s.is_high]
    lows = [s for s in swings if not s.is_high]

    hh, hl, lh, ll = [], [], [], []

    for i in range(1, len(highs)):
        if highs[i].price > highs[i - 1].price:
            hh.append(highs[i])
        else:
            lh.append(highs[i])

    for i in range(1, len(lows)):
        if lows[i].price > lows[i - 1].price:
            hl.append(lows[i])
        else:
            ll.append(lows[i])

    last_swing = swings[-1] if swings else SwingPoint(0, datetime.now(), True, timeframe)

    # Determine bias
    if len(hh) > len(lh) and len(hl) > len(ll):
        bias = "bullish"
    elif len(lh) > len(hh) and len(ll) > len(hl):
        bias = "bearish"
    else:
        bias = "ranging"

    return MarketStructure(
        higher_highs=hh,
        higher_lows=hl,
        lower_highs=lh,
        lower_lows=ll,
        last_swing=last_swing,
        bias=bias,
        timeframe=timeframe,
    )


def get_h1_bias(ohlcv_h1: pd.DataFrame) -> str:
    """Extract H1 market bias for filter."""
    structure = build_market_structure(ohlcv_h1, "H1")
    return structure.bias


def get_m15_structure(ohlcv_m15: pd.DataFrame) -> MarketStructure:
    """Get M15 trend structure."""
    return build_market_structure(ohlcv_m15, "M15")


def get_m5_execution_context(ohlcv_m5: pd.DataFrame) -> dict:
    """M5 execution context - recent price action for entry timing."""
    if len(ohlcv_m5) < 10:
        return {"ready": False, "structure": None}

    structure = build_market_structure(ohlcv_m5, "M5", lookback=5)
    return {
        "ready": True,
        "structure": structure,
        "last_close": float(ohlcv_m5["close"].iloc[-1]),
        "last_high": float(ohlcv_m5["high"].iloc[-1]),
        "last_low": float(ohlcv_m5["low"].iloc[-1]),
    }
