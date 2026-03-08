"""
Trade management: TP1=1R, TP2=1.5R, TP3=2R, break-even after TP1.
"""
from config import settings


def get_tp_levels(entry: float, stop_loss: float, direction: str) -> tuple[float, float, float]:
    """Compute TP1, TP2, TP3 in price terms."""
    risk = abs(entry - stop_loss)
    if direction.lower() in ("long", "buy"):
        tp1 = entry + risk * settings.TP1_R
        tp2 = entry + risk * settings.TP2_R
        tp3 = entry + risk * settings.TP3_R
    else:
        tp1 = entry - risk * settings.TP1_R
        tp2 = entry - risk * settings.TP2_R
        tp3 = entry - risk * settings.TP3_R
    return tp1, tp2, tp3


def get_break_even_level(entry: float, direction: str, buffer_pips: float = 0.0001) -> float:
    """Break-even = entry + small buffer to avoid slippage."""
    if direction.lower() in ("long", "buy"):
        return entry + buffer_pips
    return entry - buffer_pips


def should_move_to_breakeven(tp1_hit: bool) -> bool:
    """After TP1 is hit, move SL to break-even."""
    return tp1_hit
