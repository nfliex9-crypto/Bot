from __future__ import annotations


def should_kill(drawdown: float, threshold: float) -> bool:
    return drawdown <= -abs(threshold)
