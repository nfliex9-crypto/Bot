"""
Strategy Discovery Engine — main orchestrator.

Pipeline:
  1. Generate synthetic OHLCV data (or accept external data).
  2. Generate 200+ strategy configurations.
  3. Pre-compute indicators on the full dataset.
  4. First pass: backtest all strategies on full data, filter by metrics.
  5. Second pass: walk-forward validation on survivors.
  6. Rank surviving strategies by composite score.
  7. Export top 5 strategies with full reports.
  8. Convert the best strategy into a trading-engine module.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.discovery.backtest import BacktestConfig, prepare_dataframe, run_backtest
from app.discovery.exporter import export_top_strategies
from app.discovery.filters import filter_batch
from app.discovery.generator import generate_strategies
from app.discovery.integration import generate_strategy_module
from app.discovery.metrics import PerformanceReport, compute_metrics
from app.discovery.ranking import RankedStrategy, rank_strategies
from app.discovery.strategy_config import StrategyConfig
from app.discovery.validation import ValidationResult, walk_forward_validate


def generate_ohlcv(
    n_candles: int = 5000,
    timeframe_minutes: int = 5,
    seed: int = 42,
    base_price: float = 1.1000,
    volatility: float = 0.0002,
) -> pd.DataFrame:
    """
    Generate synthetic OHLCV data with regime changes (trend-up,
    trend-down, ranging) for strategy backtesting.
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range(
        end=pd.Timestamp.now(tz="UTC"),
        periods=n_candles,
        freq=f"{timeframe_minutes}min",
    )

    prices = [base_price]
    regime = "trend_up"
    regime_length = 0

    for i in range(1, n_candles):
        regime_length += 1
        if regime_length > rng.integers(40, 120):
            regime = rng.choice(["trend_up", "trend_down", "ranging", "volatile"])
            regime_length = 0

        if regime == "trend_up":
            change = rng.normal(volatility * 0.3, volatility)
        elif regime == "trend_down":
            change = rng.normal(-volatility * 0.3, volatility)
        elif regime == "volatile":
            change = rng.normal(0, volatility * 2.0)
        else:
            change = rng.normal(0, volatility * 0.5)

        prices.append(max(prices[-1] + change, 0.0001))

    rows = []
    for i, (dt, close) in enumerate(zip(dates, prices)):
        high_extra = rng.uniform(0, 2.0) * volatility
        low_extra = rng.uniform(0, 2.0) * volatility
        open_price = prices[i - 1] if i > 0 else close
        rows.append({
            "time": dt,
            "open": open_price,
            "high": max(open_price, close) + high_extra,
            "low": min(open_price, close) - low_extra,
            "close": close,
            "volume": float(rng.integers(100, 10000)),
        })

    return pd.DataFrame(rows)


@dataclass
class DiscoveryReport:
    total_generated: int = 0
    passed_first_filter: int = 0
    passed_walkforward: int = 0
    total_ranked: int = 0
    top_strategies: List[RankedStrategy] = field(default_factory=list)
    module_path: Optional[str] = None
    export_dir: Optional[str] = None
    elapsed_seconds: float = 0.0


class DiscoveryEngine:
    """Orchestrates the full strategy discovery pipeline."""

    def __init__(
        self,
        n_candles: int = 20_000,
        n_strategies: int = 200,
        seed: int = 42,
        bt_cfg: Optional[BacktestConfig] = None,
        output_dir: str = "output/discovery",
        verbose: bool = True,
    ):
        self.n_candles = n_candles
        self.n_strategies = n_strategies
        self.seed = seed
        self.bt_cfg = bt_cfg or BacktestConfig()
        self.output_dir = output_dir
        self.verbose = verbose

    def _log(self, msg: str):
        if self.verbose:
            print(msg)

    def run(
        self,
        df: Optional[pd.DataFrame] = None,
        top_n: int = 5,
    ) -> DiscoveryReport:
        """
        Execute the complete discovery pipeline.

        Args:
            df: Pre-existing OHLCV DataFrame.  If None, synthetic data is
                generated.
            top_n: Number of top strategies to export.

        Returns:
            DiscoveryReport with all results.
        """
        t0 = time.time()
        report = DiscoveryReport()

        # ── 1. Data ──────────────────────────────────────────
        if df is None:
            self._log("[1/8] Generating synthetic OHLCV data "
                      f"({self.n_candles} bars)...")
            df = generate_ohlcv(
                n_candles=self.n_candles,
                seed=self.seed,
            )
        else:
            self._log(f"[1/8] Using provided data ({len(df)} bars)...")

        # ── 2. Generate strategies ───────────────────────────
        self._log(f"[2/8] Generating {self.n_strategies}+ strategies...")
        strategies = generate_strategies(target=self.n_strategies, seed=self.seed)
        report.total_generated = len(strategies)
        self._log(f"       Generated {len(strategies)} strategies across "
                  f"{len(set(s.family for s in strategies))} families")

        # ── 3. Compute indicators ────────────────────────────
        self._log("[3/8] Computing indicators...")
        df_prepared = prepare_dataframe(df)

        # ── 4. First pass: backtest + filter ─────────────────
        self._log("[4/8] Backtesting all strategies (first pass)...")
        first_pass_results: List[Tuple[StrategyConfig, PerformanceReport]] = []

        for idx, strat in enumerate(strategies):
            if self.verbose and (idx + 1) % 50 == 0:
                self._log(f"       ... {idx + 1}/{len(strategies)}")
            trades, eq = run_backtest(strat, df_prepared, self.bt_cfg)
            perf = compute_metrics(trades, eq, len(df_prepared))
            first_pass_results.append((strat, perf))

        # ── 5. Filter ───────────────────────────────────────
        self._log("[5/8] Filtering strategies...")
        passed, rejected = filter_batch(first_pass_results)
        report.passed_first_filter = len(passed)
        self._log(f"       {len(passed)} passed / {len(rejected)} rejected")

        # ── 6. Walk-forward validation ───────────────────────
        self._log(f"[6/8] Walk-forward validation on {len(passed)} survivors...")
        validation_results: List[ValidationResult] = []

        for idx, fr in enumerate(passed):
            if self.verbose and (idx + 1) % 10 == 0:
                self._log(f"       ... {idx + 1}/{len(passed)}")
            vr = walk_forward_validate(
                fr.strategy, df_prepared, self.bt_cfg,
            )
            validation_results.append(vr)

        wf_survived = [v for v in validation_results if v.survived]
        report.passed_walkforward = len(wf_survived)
        self._log(f"       {len(wf_survived)} survived walk-forward validation")

        # ── 7. Rank ──────────────────────────────────────────
        self._log("[7/8] Ranking strategies...")
        ranked = rank_strategies(validation_results)
        report.total_ranked = len(ranked)
        report.top_strategies = ranked[:top_n]

        if ranked:
            self._log(f"       Top strategy: {ranked[0].strategy.name} "
                      f"(score={ranked[0].composite_score:.4f})")
        else:
            self._log("       No strategies survived the full pipeline.")

        # ── 8. Export + Integration ──────────────────────────
        self._log("[8/8] Exporting results...")
        if ranked:
            export_dir = export_top_strategies(ranked, top_n, self.output_dir)
            report.export_dir = export_dir

            module_path = generate_strategy_module(ranked[0])
            report.module_path = module_path
            self._log(f"       Module generated: {module_path}")
        else:
            self._log("       Nothing to export.")

        report.elapsed_seconds = round(time.time() - t0, 2)
        self._log(f"\nDiscovery complete in {report.elapsed_seconds}s")
        self._print_summary(report)

        return report

    def _print_summary(self, report: DiscoveryReport):
        if not self.verbose:
            return

        print("\n" + "=" * 70)
        print("STRATEGY DISCOVERY ENGINE — SUMMARY")
        print("=" * 70)
        print(f"  Strategies generated:       {report.total_generated}")
        print(f"  Passed first filter:        {report.passed_first_filter}")
        print(f"  Passed walk-forward:        {report.passed_walkforward}")
        print(f"  Final ranked:               {report.total_ranked}")
        print(f"  Time elapsed:               {report.elapsed_seconds}s")

        if report.top_strategies:
            print(f"\n  TOP {len(report.top_strategies)} STRATEGIES:")
            print(f"  {'Rank':<6}{'Name':<30}{'Score':<10}{'Sharpe':<10}"
                  f"{'PF':<10}{'DD':<10}{'Family'}")
            print("  " + "-" * 90)
            for i, rs in enumerate(report.top_strategies, 1):
                oos = rs.oos_report
                print(
                    f"  {i:<6}"
                    f"{rs.strategy.name:<30}"
                    f"{rs.composite_score:<10.4f}"
                    f"{oos.sharpe_ratio:<10.2f}"
                    f"{oos.profit_factor:<10.2f}"
                    f"{oos.max_drawdown:<10.2%}"
                    f"{rs.strategy.family}"
                )

        if report.module_path:
            print(f"\n  Best strategy module: {report.module_path}")
        if report.export_dir:
            print(f"  Full reports:         {report.export_dir}/")
        print("=" * 70)
