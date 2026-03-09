"""
Alpha Discovery Pipeline Orchestrator.

End-to-end pipeline that orchestrates all engines: data ingestion,
feature engineering, strategy generation, backtesting, validation,
selection, portfolio construction, and deployment.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import pandas as pd

from ..backtest.engine import BacktestEngine
from ..backtest.results import BacktestResult
from ..config import EngineConfig
from ..data.ingestion import DataIngestionPipeline
from ..execution.engine import ExecutionEngine
from ..features.engine import FeatureEngine
from ..monitoring.anomaly import AnomalyDetector
from ..monitoring.dashboard import PerformanceDashboard
from ..monitoring.health import StrategyHealthMonitor
from ..portfolio.optimizer import PortfolioOptimizer, PortfolioResult
from ..risk.manager import RiskManager
from ..selection.selector import SelectionResult, StrategySelector
from ..strategy.generator import StrategyGenerator
from ..strategy.universe import StrategyUniverse
from ..validation.monte_carlo import MonteCarloValidator
from ..validation.statistical import StatisticalValidator
from ..validation.walk_forward import WalkForwardValidator

logger = logging.getLogger(__name__)


class PipelineStage(Enum):
    DATA_INGESTION = "data_ingestion"
    FEATURE_ENGINEERING = "feature_engineering"
    STRATEGY_GENERATION = "strategy_generation"
    BACKTESTING = "backtesting"
    VALIDATION = "validation"
    SELECTION = "selection"
    PORTFOLIO_CONSTRUCTION = "portfolio_construction"
    DEPLOYMENT = "deployment"


@dataclass
class PipelineResult:
    """Complete output of the alpha discovery pipeline."""
    run_id: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    duration_seconds: float = 0.0

    n_symbols: int = 0
    n_features_generated: int = 0
    n_strategies_generated: int = 0
    n_strategies_backtested: int = 0
    n_strategies_validated: int = 0
    n_strategies_selected: int = 0

    universe: Optional[StrategyUniverse] = None
    backtest_results: list[BacktestResult] = field(default_factory=list)
    selection_result: Optional[SelectionResult] = None
    portfolio: Optional[PortfolioResult] = None

    stage_timings: dict[str, float] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "duration_seconds": self.duration_seconds,
            "n_symbols": self.n_symbols,
            "n_features": self.n_features_generated,
            "n_generated": self.n_strategies_generated,
            "n_backtested": self.n_strategies_backtested,
            "n_validated": self.n_strategies_validated,
            "n_selected": self.n_strategies_selected,
            "portfolio_sharpe": self.portfolio.expected_sharpe if self.portfolio else None,
            "portfolio_vol": self.portfolio.expected_volatility if self.portfolio else None,
            "stage_timings": self.stage_timings,
            "n_errors": len(self.errors),
        }


class AlphaDiscoveryPipeline:
    """
    Master orchestrator for the entire alpha discovery lifecycle.

    Coordinates all sub-engines in the correct order, manages data flow
    between stages, and produces a deployable portfolio of strategies.

    Usage:
        config = EngineConfig()
        pipeline = AlphaDiscoveryPipeline(config)
        result = pipeline.run()
    """

    def __init__(self, config: Optional[EngineConfig] = None) -> None:
        self.config = config or EngineConfig()

        self.data_pipeline = DataIngestionPipeline(self.config.data)
        self.feature_engine = FeatureEngine(self.config.features)
        self.strategy_generator = StrategyGenerator(self.config.strategy)
        self.backtest_engine = BacktestEngine(self.config.backtest)
        self.stat_validator = StatisticalValidator(self.config.validation)
        self.wf_validator = WalkForwardValidator(self.config.validation)
        self.mc_validator = MonteCarloValidator(self.config.validation)
        self.selector = StrategySelector(self.config.validation)
        self.portfolio_optimizer = PortfolioOptimizer(self.config.portfolio)
        self.risk_manager = RiskManager(self.config.risk)
        self.execution_engine = ExecutionEngine(self.config.execution, risk_manager=self.risk_manager)
        self.dashboard = PerformanceDashboard()
        self.anomaly_detector = AnomalyDetector(self.config.monitoring.anomaly_zscore_threshold)
        self.health_monitor = StrategyHealthMonitor()

        self._data: dict[str, pd.DataFrame] = {}
        self._features: dict[str, pd.DataFrame] = {}

    def run(
        self,
        symbols: Optional[list[str]] = None,
        provider: str = "synthetic",
        max_strategies: int = 30,
    ) -> PipelineResult:
        """
        Execute the full alpha discovery pipeline.

        Stages:
        1. Ingest market data
        2. Generate features
        3. Generate candidate strategies
        4. Backtest all candidates
        5. Validate with statistical tests
        6. Select robust strategies
        7. Construct optimal portfolio
        """
        import uuid
        result = PipelineResult(
            run_id=str(uuid.uuid4())[:8],
            start_time=time.time(),
        )

        symbols = symbols or self.config.data.base_symbols

        try:
            result = self._stage_data_ingestion(result, symbols, provider)
            result = self._stage_feature_engineering(result)
            result = self._stage_strategy_generation(result, symbols)
            result = self._stage_backtesting(result)
            result = self._stage_selection(result, max_strategies)
            result = self._stage_portfolio_construction(result)
        except Exception as e:
            logger.error("Pipeline failed: %s", e, exc_info=True)
            result.errors.append(str(e))

        result.end_time = time.time()
        result.duration_seconds = result.end_time - result.start_time

        logger.info("=" * 70)
        logger.info("PIPELINE COMPLETE: %s", result.run_id)
        logger.info("Duration: %.1fs", result.duration_seconds)
        logger.info("Strategies: %d generated -> %d backtested -> %d selected",
                     result.n_strategies_generated, result.n_strategies_backtested,
                     result.n_strategies_selected)
        if result.portfolio:
            logger.info("Portfolio Sharpe: %.2f | Vol: %.1f%% | Strategies: %d",
                         result.portfolio.expected_sharpe,
                         result.portfolio.expected_volatility * 100,
                         len(result.portfolio.weights))
        logger.info("=" * 70)

        return result

    def _stage_data_ingestion(
        self, result: PipelineResult, symbols: list[str], provider: str,
    ) -> PipelineResult:
        t0 = time.time()
        logger.info("STAGE 1: Data Ingestion (%d symbols)", len(symbols))

        self._data = self.data_pipeline.ingest(
            symbols=symbols, timeframe="1d", provider_name=provider,
        )
        result.n_symbols = len(self._data)
        result.stage_timings[PipelineStage.DATA_INGESTION.value] = time.time() - t0

        logger.info("  Ingested %d symbols, avg %d bars",
                     len(self._data),
                     int(sum(len(d) for d in self._data.values()) / max(len(self._data), 1)))
        return result

    def _stage_feature_engineering(self, result: PipelineResult) -> PipelineResult:
        t0 = time.time()
        logger.info("STAGE 2: Feature Engineering")

        self._features = self.feature_engine.build_feature_matrix(self._data)
        n_feats = max(len(df.columns) for df in self._features.values()) if self._features else 0
        result.n_features_generated = n_feats
        result.stage_timings[PipelineStage.FEATURE_ENGINEERING.value] = time.time() - t0

        logger.info("  Generated %d features per symbol", n_feats)
        return result

    def _stage_strategy_generation(
        self, result: PipelineResult, symbols: list[str],
    ) -> PipelineResult:
        t0 = time.time()
        logger.info("STAGE 3: Strategy Generation")

        first_features = list(self._features.values())[0] if self._features else pd.DataFrame()
        feature_names = list(first_features.columns) if not first_features.empty else []

        universe = self.strategy_generator.generate_all(symbols, feature_names)
        result.universe = universe
        result.n_strategies_generated = universe.size
        result.stage_timings[PipelineStage.STRATEGY_GENERATION.value] = time.time() - t0

        logger.info("  Generated %d unique strategies", universe.size)
        logger.info("  Breakdown: %s", universe.summary())
        return result

    def _stage_backtesting(self, result: PipelineResult) -> PipelineResult:
        t0 = time.time()
        logger.info("STAGE 4: Backtesting")

        if result.universe is None:
            return result

        all_specs = result.universe.all()
        bt_results = self.backtest_engine.run_batch(
            all_specs, self._data, self._features,
        )

        valid_results = [r for r in bt_results if r.metrics and r.metrics.sharpe_ratio != 0]
        result.backtest_results = valid_results
        result.n_strategies_backtested = len(valid_results)
        result.stage_timings[PipelineStage.BACKTESTING.value] = time.time() - t0

        if valid_results:
            sharpes = [r.metrics.sharpe_ratio for r in valid_results if r.metrics]
            logger.info("  Backtested %d strategies", len(valid_results))
            logger.info("  Sharpe distribution: min=%.2f, median=%.2f, max=%.2f",
                         min(sharpes), sorted(sharpes)[len(sharpes)//2], max(sharpes))
        return result

    def _stage_selection(
        self, result: PipelineResult, max_strategies: int,
    ) -> PipelineResult:
        t0 = time.time()
        logger.info("STAGE 5: Strategy Selection")

        selected, selection_result = self.selector.select(
            result.backtest_results,
            max_strategies=max_strategies,
            max_correlation=self.config.validation.max_correlation,
        )

        result.backtest_results = selected
        result.selection_result = selection_result
        result.n_strategies_selected = len(selected)
        result.stage_timings[PipelineStage.SELECTION.value] = time.time() - t0

        logger.info("  Selected %d strategies from %d candidates",
                     len(selected), selection_result.total_candidates)
        logger.info("  Filter funnel: %d -> %d -> %d -> %d -> %d",
                     selection_result.total_candidates,
                     selection_result.after_minimum_filter,
                     selection_result.after_statistical_filter,
                     selection_result.after_robustness_filter,
                     selection_result.after_correlation_filter)
        return result

    def _stage_portfolio_construction(self, result: PipelineResult) -> PipelineResult:
        t0 = time.time()
        logger.info("STAGE 6: Portfolio Construction")

        if not result.backtest_results:
            logger.warning("  No strategies to build portfolio from")
            return result

        portfolio = self.portfolio_optimizer.optimize(result.backtest_results)
        result.portfolio = portfolio
        result.stage_timings[PipelineStage.PORTFOLIO_CONSTRUCTION.value] = time.time() - t0

        logger.info("  Portfolio: %d strategies, Sharpe=%.2f, Vol=%.1f%%",
                     len(portfolio.weights), portfolio.expected_sharpe,
                     portfolio.expected_volatility * 100)
        logger.info("  Diversification ratio: %.2f", portfolio.diversification_ratio)
        logger.info("  Gross leverage: %.2f, Net leverage: %.2f",
                     portfolio.gross_leverage, portfolio.net_leverage)

        return result

    def deploy(self, result: PipelineResult) -> bool:
        """Deploy selected strategies to the execution engine."""
        if result.portfolio is None or not result.portfolio.weights:
            logger.warning("No portfolio to deploy")
            return False

        logger.info("STAGE 7: Deployment")
        initialized = self.execution_engine.initialize()
        if not initialized:
            logger.error("Execution engine failed to initialize")
            return False

        logger.info("  Deployed %d strategies for live execution", len(result.portfolio.weights))
        for sid, weight in sorted(result.portfolio.weights.items(), key=lambda x: -abs(x[1])):
            logger.info("    %s: %.1f%%", sid, weight * 100)

        return True
