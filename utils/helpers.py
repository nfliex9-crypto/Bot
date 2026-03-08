from __future__ import annotations

import hashlib
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_trade_id(symbol: str, direction: str) -> str:
    raw = f"{symbol}_{direction}_{time.time()}_{uuid.uuid4().hex[:8]}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16].upper()


def round_price(price: float, decimals: int = 5) -> float:
    return round(price, decimals)


def pips_to_price(pips: float, symbol: str) -> float:
    """Convert pip value to price distance for common pairs."""
    if "JPY" in symbol.upper():
        return pips * 0.01
    return pips * 0.0001


def price_to_pips(price_diff: float, symbol: str) -> float:
    if "JPY" in symbol.upper():
        return abs(price_diff) / 0.01
    return abs(price_diff) / 0.0001


def calculate_lot_size(
    account_balance: float,
    risk_pct: float,
    stop_loss_pips: float,
    pip_value_per_lot: float = 10.0,
    min_lot: float = 0.01,
    max_lot: float = 10.0,
    lot_step: float = 0.01,
) -> float:
    risk_amount = account_balance * risk_pct
    if stop_loss_pips <= 0 or pip_value_per_lot <= 0:
        return min_lot
    raw_lot = risk_amount / (stop_loss_pips * pip_value_per_lot)
    lot = max(min_lot, min(max_lot, raw_lot))
    lot = round(round(lot / lot_step) * lot_step, 2)
    return lot


def calculate_crypto_quantity(
    account_balance: float,
    risk_pct: float,
    entry_price: float,
    stop_loss_price: float,
    min_qty: float = 0.001,
    qty_step: float = 0.001,
) -> float:
    risk_amount = account_balance * risk_pct
    sl_distance = abs(entry_price - stop_loss_price)
    if sl_distance <= 0:
        return min_qty
    raw_qty = risk_amount / sl_distance
    qty = max(min_qty, raw_qty)
    qty = round(round(qty / qty_step) * qty_step, 6)
    return qty


def ewm_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Exponentially weighted ATR."""
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def find_swing_highs(series: pd.Series, lookback: int = 5) -> pd.Series:
    """Returns boolean Series where True = swing high."""
    result = pd.Series(False, index=series.index)
    for i in range(lookback, len(series) - lookback):
        window = series.iloc[i - lookback : i + lookback + 1]
        if series.iloc[i] == window.max():
            result.iloc[i] = True
    return result


def find_swing_lows(series: pd.Series, lookback: int = 5) -> pd.Series:
    """Returns boolean Series where True = swing low."""
    result = pd.Series(False, index=series.index)
    for i in range(lookback, len(series) - lookback):
        window = series.iloc[i - lookback : i + lookback + 1]
        if series.iloc[i] == window.min():
            result.iloc[i] = True
    return result


def fib_retracement_levels(
    swing_low: float, swing_high: float, direction: str = "long"
) -> dict[str, float]:
    diff = swing_high - swing_low
    if direction == "long":
        return {
            "0.236": swing_high - diff * 0.236,
            "0.382": swing_high - diff * 0.382,
            "0.500": swing_high - diff * 0.500,
            "0.618": swing_high - diff * 0.618,
            "0.786": swing_high - diff * 0.786,
        }
    return {
        "0.236": swing_low + diff * 0.236,
        "0.382": swing_low + diff * 0.382,
        "0.500": swing_low + diff * 0.500,
        "0.618": swing_low + diff * 0.618,
        "0.786": swing_low + diff * 0.786,
    }


def serialize_signals(signals: dict[str, Any]) -> str:
    import json
    return json.dumps(signals, default=str)
