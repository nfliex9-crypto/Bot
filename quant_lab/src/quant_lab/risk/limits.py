from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskLimits:
    max_gross: float
    max_net: float
    max_symbol_weight: float
    kill_switch_dd: float
