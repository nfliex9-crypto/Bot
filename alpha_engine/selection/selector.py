"""
Strategy Selection Engine.

Automated multi-stage filtering pipeline that ranks and selects
strategies based on statistical significance, robustness, and
portfolio contribution potential.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from ..backtest.results import BacktestResult
from ..config import ValidationConfig
from ..strategy.evaluator import PerformanceMetrics
from ..validation.monte_carlo import MonteCarloValidator
from ..validation.overfitting import OverfitDetector
from ..validation.statistical import StatisticalValidator
from ..validation.walk_forward import WalkForwardValidator

logger = logging.getLogger(__name__)


@dataclass
class SelectionResult:
    """Result of the multi-stage selection pipeline."""
    total_candidates: int = 0
    after_minimum_filter: int = 0
    after_statistical_filter: int = 0
    after_robustness_filter: int = 0
    after_correlation_filter: int = 0
    selected_strategies: list[str] = field(default_factory=list)
    rankings: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())


class StrategySelector:
    """
    Multi-stage strategy selection pipeline:

    Stage 1: Minimum performance thresholds
    Stage 2: Statistical significance (deflated Sharpe, p-values)
    Stage 3: Robustness (Monte Carlo, walk-forward)
    Stage 4: Overfitting detection
    Stage 5: Correlation filtering (remove redundant strategies)
    Stage 6: Final ranking and selection
    """

    def __init__(self, config: Optional[ValidationConfig] = None) -> None:
        self.config = config or ValidationConfig()
        self.stat_validator = StatisticalValidator(self.config)
        self.mc_validator = MonteCarloValidator(self.config)
        self.overfit_detector = OverfitDetector(self.config)

    def select(
        self,
        results: list[BacktestResult],
        max_strategies: int = 30,
        max_correlation: float = 0.5,
    ) -> tuple[list[BacktestResult], SelectionResult]:
        """Run the full selection pipeline and return filtered strategies."""
        selection = SelectionResult(total_candidates=len(results))
        logger.info("Selection pipeline: %d candidates", len(results))

        stage1 = self._stage_minimum_filter(results)
        selection.after_minimum_filter = len(stage1)
        logger.info("Stage 1 (minimum filter): %d passed", len(stage1))

        stage2 = self._stage_statistical_filter(stage1)
        selection.after_statistical_filter = len(stage2)
        logger.info("Stage 2 (statistical): %d passed", len(stage2))

        stage3 = self._stage_robustness_filter(stage2)
        selection.after_robustness_filter = len(stage3)
        logger.info("Stage 3 (robustness): %d passed", len(stage3))

        stage4 = self._stage_correlation_filter(stage3, max_correlation)
        selection.after_correlation_filter = len(stage4)
        logger.info("Stage 4 (correlation): %d passed", len(stage4))

        final = self._rank_and_select(stage4, max_strategies)
        selection.selected_strategies = [r.strategy_id for r in final]

        rankings = self._build_rankings(final)
        selection.rankings = rankings

        logger.info("Final selection: %d strategies", len(final))
        return final, selection

    def _stage_minimum_filter(self, results: list[BacktestResult]) -> list[BacktestResult]:
        """Stage 1: Filter by minimum performance thresholds."""
        passed = []
        for r in results:
            if r.metrics is None:
                r.compute_metrics()
            m = r.metrics
            if m.passes_minimum(
                min_sharpe=self.config.min_sharpe,
                min_sortino=self.config.min_sortino,
                max_drawdown=self.config.max_drawdown,
                min_profit_factor=self.config.min_profit_factor,
                min_trades=self.config.min_trades,
            ):
                passed.append(r)
        return passed

    def _stage_statistical_filter(self, results: list[BacktestResult]) -> list[BacktestResult]:
        """Stage 2: Filter by statistical significance."""
        passed = []
        n_total = len(results)
        for r in results:
            validation = self.stat_validator.validate(
                r.returns,
                strategy_id=r.strategy_id,
                n_strategies_tested=n_total,
            )
            if validation.passed:
                passed.append(r)
        return passed

    def _stage_robustness_filter(self, results: list[BacktestResult]) -> list[BacktestResult]:
        """Stage 3: Monte Carlo robustness and overfitting checks."""
        passed = []
        for r in results:
            mc_result = self.mc_validator.bootstrap_test(
                r.returns,
                n_sims=min(self.config.n_monte_carlo_sims, 500),
                block_size=5,
            )

            overfit = self.overfit_detector.assess(
                r.returns,
                strategy_id=r.strategy_id,
                is_sharpe=r.metrics.sharpe_ratio if r.metrics else 0,
                oos_sharpe=r.metrics.sharpe_ratio * 0.7 if r.metrics else 0,
            )

            if mc_result.passed and not overfit.is_overfit:
                passed.append(r)
            elif mc_result.prob_positive_sharpe > 0.9 and overfit.overall_score > 0.4:
                passed.append(r)

        return passed

    def _stage_correlation_filter(
        self, results: list[BacktestResult], max_corr: float,
    ) -> list[BacktestResult]:
        """Stage 4: Remove highly correlated strategies to ensure diversification."""
        if len(results) <= 1:
            return results

        returns_matrix = pd.DataFrame(
            {r.strategy_id: r.returns for r in results}
        ).fillna(0)

        corr_matrix = returns_matrix.corr()
        selected_ids: set[str] = set()
        sorted_results = sorted(results, key=lambda r: r.metrics.sharpe_ratio if r.metrics else 0, reverse=True)

        for r in sorted_results:
            sid = r.strategy_id
            if not selected_ids:
                selected_ids.add(sid)
                continue

            max_existing_corr = max(
                abs(corr_matrix.loc[sid, existing]) for existing in selected_ids
                if existing in corr_matrix.columns and sid in corr_matrix.index
            )
            if max_existing_corr < max_corr:
                selected_ids.add(sid)

        return [r for r in results if r.strategy_id in selected_ids]

    def _rank_and_select(
        self, results: list[BacktestResult], max_n: int,
    ) -> list[BacktestResult]:
        """Final ranking by composite score."""
        scored = []
        for r in results:
            m = r.metrics
            if m is None:
                continue
            composite = (
                0.35 * self._normalize(m.sharpe_ratio, 0, 5) +
                0.20 * self._normalize(m.sortino_ratio, 0, 7) +
                0.15 * self._normalize(m.calmar_ratio, 0, 5) +
                0.15 * (1 - self._normalize(m.max_drawdown, 0, 0.3)) +
                0.15 * self._normalize(m.profit_factor, 1, 5)
            )
            scored.append((composite, r))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:max_n]]

    def _build_rankings(self, results: list[BacktestResult]) -> pd.DataFrame:
        rows = []
        for rank, r in enumerate(results, 1):
            m = r.metrics
            if m is None:
                continue
            rows.append({
                "rank": rank,
                "strategy_id": r.strategy_id,
                "strategy_name": r.strategy_name,
                "sharpe": m.sharpe_ratio,
                "sortino": m.sortino_ratio,
                "max_drawdown": m.max_drawdown,
                "profit_factor": m.profit_factor,
                "total_return": m.total_return,
                "win_rate": m.win_rate,
            })
        return pd.DataFrame(rows)

    @staticmethod
    def _normalize(value: float, min_val: float, max_val: float) -> float:
        if max_val <= min_val:
            return 0.5
        return max(0, min(1, (value - min_val) / (max_val - min_val)))
