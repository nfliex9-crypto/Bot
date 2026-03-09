from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StrategyHealth:
    signal_freshness_ok: bool
    drawdown_ok: bool
    latency_ok: bool
