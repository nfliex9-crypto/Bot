from __future__ import annotations

import math
from decimal import Decimal, ROUND_DOWN


def round_step(value: float, step: float) -> float:
    """Round a value down to the nearest step (for exchange lot/tick sizes)."""
    if step == 0:
        return value
    precision = max(0, -int(math.log10(step)))
    d = Decimal(str(value)).quantize(Decimal(str(step)), rounding=ROUND_DOWN)
    return float(d)


def pip_value(symbol: str) -> float:
    if "JPY" in symbol:
        return 0.01
    return 0.0001


def pips_to_price(pips: float, symbol: str) -> float:
    return pips * pip_value(symbol)
