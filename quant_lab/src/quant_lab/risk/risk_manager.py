from __future__ import annotations

from dataclasses import dataclass

from .kill_switch import should_kill
from .limits import RiskLimits


@dataclass
class RiskCheckResult:
    passed: bool
    reason: str


class RiskManager:
    def __init__(self, limits: RiskLimits) -> None:
        self.limits = limits

    def check(self, gross: float, net: float, max_symbol_weight: float, drawdown: float) -> RiskCheckResult:
        if should_kill(drawdown, self.limits.kill_switch_dd):
            return RiskCheckResult(False, "kill_switch_triggered")
        if gross > self.limits.max_gross:
            return RiskCheckResult(False, "max_gross_breach")
        if abs(net) > self.limits.max_net:
            return RiskCheckResult(False, "max_net_breach")
        if max_symbol_weight > self.limits.max_symbol_weight:
            return RiskCheckResult(False, "max_symbol_weight_breach")
        return RiskCheckResult(True, "ok")
