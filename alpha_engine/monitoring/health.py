"""
Strategy health monitoring.

Tracks strategy-level health metrics and provides recommendations
for strategy activation, deactivation, and parameter adjustment.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd

from ..strategy.evaluator import StrategyEvaluator

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    HALTED = "halted"


@dataclass
class StrategyHealth:
    """Health assessment for a single strategy."""
    strategy_id: str = ""
    status: HealthStatus = HealthStatus.HEALTHY
    sharpe_30d: float = 0.0
    sharpe_90d: float = 0.0
    current_drawdown: float = 0.0
    days_in_drawdown: int = 0
    win_rate_30d: float = 0.0
    avg_daily_return: float = 0.0
    return_stability: float = 0.0
    is_active: bool = True
    recommendation: str = ""
    last_updated: float = 0.0


class StrategyHealthMonitor:
    """
    Monitors the ongoing health of deployed strategies.

    Periodically evaluates each strategy's recent performance
    and flags degradation patterns.
    """

    def __init__(
        self,
        sharpe_warning_threshold: float = 0.5,
        sharpe_critical_threshold: float = 0.0,
        max_drawdown_warning: float = 0.05,
        max_drawdown_critical: float = 0.10,
        min_win_rate: float = 0.40,
    ) -> None:
        self.sharpe_warn = sharpe_warning_threshold
        self.sharpe_crit = sharpe_critical_threshold
        self.dd_warn = max_drawdown_warning
        self.dd_crit = max_drawdown_critical
        self.min_wr = min_win_rate
        self._health_states: dict[str, StrategyHealth] = {}

    def assess(
        self,
        strategy_id: str,
        returns: pd.Series,
    ) -> StrategyHealth:
        """Evaluate current health of a strategy from its return series."""
        health = StrategyHealth(strategy_id=strategy_id, last_updated=time.time())

        if len(returns) < 5:
            health.status = HealthStatus.HALTED
            health.recommendation = "Insufficient data"
            return health

        recent_30 = returns.tail(min(30, len(returns)))
        recent_90 = returns.tail(min(90, len(returns)))

        metrics_30 = StrategyEvaluator.evaluate(recent_30)
        metrics_90 = StrategyEvaluator.evaluate(recent_90)

        health.sharpe_30d = metrics_30.sharpe_ratio
        health.sharpe_90d = metrics_90.sharpe_ratio
        health.current_drawdown = metrics_90.max_drawdown
        health.win_rate_30d = metrics_30.win_rate
        health.avg_daily_return = recent_30.mean()

        chunks = np.array_split(returns.values, max(1, len(returns) // 21))
        chunk_means = [c.mean() for c in chunks if len(c) > 0]
        health.return_stability = 1 - (np.std(chunk_means) / max(abs(np.mean(chunk_means)), 1e-8))

        dd = StrategyEvaluator.drawdown_series(returns)
        in_dd = (dd < 0).astype(int)
        if len(in_dd) > 0 and in_dd.iloc[-1] == 1:
            dd_run = 0
            for v in reversed(in_dd.values):
                if v == 1:
                    dd_run += 1
                else:
                    break
            health.days_in_drawdown = dd_run

        health.status, health.recommendation = self._classify(health)
        health.is_active = health.status != HealthStatus.HALTED

        self._health_states[strategy_id] = health
        return health

    def _classify(self, h: StrategyHealth) -> tuple[HealthStatus, str]:
        if h.sharpe_30d < self.sharpe_crit and h.current_drawdown > self.dd_crit:
            return HealthStatus.HALTED, "Halt: negative Sharpe and deep drawdown"

        if h.sharpe_30d < self.sharpe_crit or h.current_drawdown > self.dd_crit:
            return HealthStatus.CRITICAL, "Reduce allocation; consider halting"

        if h.sharpe_30d < self.sharpe_warn or h.current_drawdown > self.dd_warn:
            return HealthStatus.DEGRADED, "Monitor closely; reduce if trend continues"

        if h.win_rate_30d < self.min_wr:
            return HealthStatus.DEGRADED, "Win rate below threshold"

        return HealthStatus.HEALTHY, "Operating normally"

    def get_all_health(self) -> dict[str, StrategyHealth]:
        return dict(self._health_states)

    def get_active_strategies(self) -> list[str]:
        return [sid for sid, h in self._health_states.items() if h.is_active]

    def get_halted_strategies(self) -> list[str]:
        return [sid for sid, h in self._health_states.items() if h.status == HealthStatus.HALTED]
