"""
Performance Dashboard — aggregated metrics and reporting.

Produces comprehensive performance reports, attribution analysis,
and portfolio-level summary statistics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd

from ..backtest.results import BacktestResult
from ..strategy.evaluator import StrategyEvaluator

logger = logging.getLogger(__name__)


@dataclass
class DashboardSnapshot:
    """Complete portfolio dashboard state."""
    timestamp: float = 0.0
    portfolio_nav: float = 0.0
    daily_return: float = 0.0
    mtd_return: float = 0.0
    ytd_return: float = 0.0
    inception_return: float = 0.0
    sharpe_30d: float = 0.0
    sharpe_90d: float = 0.0
    sharpe_inception: float = 0.0
    current_drawdown: float = 0.0
    max_drawdown: float = 0.0
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    n_active_strategies: int = 0
    n_positions: int = 0
    strategy_pnl: dict[str, float] = field(default_factory=dict)
    risk_metrics: dict[str, float] = field(default_factory=dict)


class PerformanceDashboard:
    """
    Aggregated performance monitoring and reporting dashboard.
    """

    def __init__(self) -> None:
        self._portfolio_returns: pd.Series = pd.Series(dtype=float)
        self._strategy_returns: dict[str, pd.Series] = {}
        self._snapshots: list[DashboardSnapshot] = []

    def update(
        self,
        portfolio_return: float,
        strategy_returns: dict[str, float],
        nav: float,
        gross_exposure: float = 0.0,
        net_exposure: float = 0.0,
    ) -> DashboardSnapshot:
        """Record a new data point and compute dashboard metrics."""
        import time as _time

        ts = pd.Timestamp.now()
        new_ret = pd.Series([portfolio_return], index=[ts])
        self._portfolio_returns = pd.concat([self._portfolio_returns, new_ret])

        for sid, ret in strategy_returns.items():
            if sid not in self._strategy_returns:
                self._strategy_returns[sid] = pd.Series(dtype=float)
            new = pd.Series([ret], index=[ts])
            self._strategy_returns[sid] = pd.concat([self._strategy_returns[sid], new])

        snapshot = self._compute_snapshot(nav, gross_exposure, net_exposure)
        self._snapshots.append(snapshot)
        return snapshot

    def _compute_snapshot(
        self, nav: float, gross_exp: float, net_exp: float,
    ) -> DashboardSnapshot:
        import time as _time
        rets = self._portfolio_returns

        snapshot = DashboardSnapshot(
            timestamp=_time.time(),
            portfolio_nav=nav,
            gross_exposure=gross_exp,
            net_exposure=net_exp,
            n_active_strategies=len(self._strategy_returns),
        )

        if len(rets) > 0:
            snapshot.daily_return = rets.iloc[-1]
            snapshot.inception_return = (1 + rets).prod() - 1

        if len(rets) >= 30:
            m30 = StrategyEvaluator.evaluate(rets.tail(30))
            snapshot.sharpe_30d = m30.sharpe_ratio

        if len(rets) >= 90:
            m90 = StrategyEvaluator.evaluate(rets.tail(90))
            snapshot.sharpe_90d = m90.sharpe_ratio

        if len(rets) > 1:
            full = StrategyEvaluator.evaluate(rets)
            snapshot.sharpe_inception = full.sharpe_ratio
            snapshot.max_drawdown = full.max_drawdown
            dd = StrategyEvaluator.drawdown_series(rets)
            snapshot.current_drawdown = abs(dd.iloc[-1]) if len(dd) > 0 else 0

        if isinstance(rets.index, pd.DatetimeIndex) and len(rets) > 0:
            now = rets.index[-1]
            month_mask = rets.index.month == now.month
            year_mask = rets.index.year == now.year
            if month_mask.any():
                snapshot.mtd_return = (1 + rets[month_mask]).prod() - 1
            if year_mask.any():
                snapshot.ytd_return = (1 + rets[year_mask]).prod() - 1

        snapshot.strategy_pnl = {
            sid: float((1 + s).prod() - 1) if len(s) > 0 else 0
            for sid, s in self._strategy_returns.items()
        }

        return snapshot

    def generate_report(self) -> dict[str, Any]:
        """Generate a comprehensive performance report."""
        rets = self._portfolio_returns
        if len(rets) < 2:
            return {"status": "insufficient_data", "n_observations": len(rets)}

        full_metrics = StrategyEvaluator.evaluate(rets)

        strategy_metrics = {}
        for sid, s_rets in self._strategy_returns.items():
            if len(s_rets) > 5:
                sm = StrategyEvaluator.evaluate(s_rets)
                strategy_metrics[sid] = sm.to_dict()

        monthly = None
        if isinstance(rets.index, pd.DatetimeIndex):
            try:
                monthly = rets.groupby(pd.Grouper(freq="ME")).sum()
                monthly = monthly.to_dict()
            except Exception:
                pass

        return {
            "portfolio": full_metrics.to_dict(),
            "strategies": strategy_metrics,
            "monthly_returns": monthly,
            "n_strategies": len(self._strategy_returns),
            "n_observations": len(rets),
        }

    def get_equity_curve(self) -> pd.Series:
        if self._portfolio_returns.empty:
            return pd.Series(dtype=float)
        return (1 + self._portfolio_returns).cumprod()

    def get_drawdown_curve(self) -> pd.Series:
        return StrategyEvaluator.drawdown_series(self._portfolio_returns)

    def get_rolling_sharpe(self, window: int = 63) -> pd.Series:
        return StrategyEvaluator.rolling_sharpe(self._portfolio_returns, window)
