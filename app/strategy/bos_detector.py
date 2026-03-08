from __future__ import annotations

from app.analysis.market_structure import Bias, StructureBreak, StructureResult


def confirm_bos(
    m15_structure: StructureResult,
    h1_bias: Bias,
    required_direction: str,
) -> dict | None:
    """
    Check whether the M15 structure has a confirmed BOS that aligns with
    both the H1 bias and the sweep direction.

    Returns the confirming BOS event dict or None.
    """
    if not m15_structure.structure_breaks:
        return None

    target_types: set[str] = set()
    if required_direction == "long" and h1_bias == Bias.BULLISH:
        target_types = {StructureBreak.BOS_BULLISH.value, StructureBreak.CHOCH_BULLISH.value}
    elif required_direction == "short" and h1_bias == Bias.BEARISH:
        target_types = {StructureBreak.BOS_BEARISH.value, StructureBreak.CHOCH_BEARISH.value}
    else:
        return None

    for brk in reversed(m15_structure.structure_breaks[-5:]):
        if brk["type"] in target_types:
            return brk

    return None
