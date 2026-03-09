"""
Walk-forward validation.

Splits data into three periods:
  1. Training   (60 %)  —  initial strategy evaluation
  2. Validation (20 %)  —  confirms training-period edge
  3. Out-of-sample test (20 %) — final robustness check

A strategy must pass filter criteria on ALL three periods to survive.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd

from app.discovery.backtest import BacktestConfig, prepare_dataframe, run_backtest
from app.discovery.filters import apply_filters
from app.discovery.metrics import PerformanceReport, compute_metrics
from app.discovery.strategy_config import StrategyConfig

TRAIN_FRAC = 0.60
VAL_FRAC = 0.20


@dataclass
class ValidationResult:
    strategy: StrategyConfig
    train_report: Optional[PerformanceReport] = None
    val_report: Optional[PerformanceReport] = None
    oos_report: Optional[PerformanceReport] = None
    passed_train: bool = False
    passed_val: bool = False
    passed_oos: bool = False
    survived: bool = False


def walk_forward_validate(
    strategy: StrategyConfig,
    df: pd.DataFrame,
    bt_cfg: Optional[BacktestConfig] = None,
    min_pf: float = 1.5,
    min_sharpe: float = 1.0,
    max_dd: float = 0.15,
    min_trades: int = 10,
) -> ValidationResult:
    """
    Run walk-forward validation on a single strategy.

    *df* should already have indicators + derived columns computed.
    *min_trades* is intentionally lower per-period than the full-data
    filter because each sub-period has fewer bars.
    """
    n = len(df)
    train_end = int(n * TRAIN_FRAC)
    val_end = int(n * (TRAIN_FRAC + VAL_FRAC))

    train_df = df.iloc[:train_end].copy()
    val_df = df.iloc[train_end:val_end].copy()
    oos_df = df.iloc[val_end:].copy()

    result = ValidationResult(strategy=strategy)

    if bt_cfg is None:
        bt_cfg = BacktestConfig()

    per_period_bt = BacktestConfig(
        initial_balance=bt_cfg.initial_balance,
        cost_per_trade_r=bt_cfg.cost_per_trade_r,
        slippage_atr_mult=bt_cfg.slippage_atr_mult,
        warmup_bars=min(bt_cfg.warmup_bars, len(train_df) // 4),
        risk_pct=bt_cfg.risk_pct,
    )

    # ── Training ──
    trades, eq = run_backtest(strategy, train_df, per_period_bt)
    result.train_report = compute_metrics(trades, eq, len(train_df))
    fr = apply_filters(strategy, result.train_report,
                       min_pf=min_pf, min_sharpe=min_sharpe,
                       max_dd=max_dd, min_trades=min_trades)
    result.passed_train = fr.passed
    if not result.passed_train:
        return result

    # ── Validation ──
    per_period_bt.warmup_bars = min(per_period_bt.warmup_bars, len(val_df) // 4)
    trades, eq = run_backtest(strategy, val_df, per_period_bt)
    result.val_report = compute_metrics(trades, eq, len(val_df))
    fr = apply_filters(strategy, result.val_report,
                       min_pf=min_pf, min_sharpe=min_sharpe * 0.8,
                       max_dd=max_dd * 1.2, min_trades=max(5, min_trades // 2))
    result.passed_val = fr.passed
    if not result.passed_val:
        return result

    # ── Out-of-sample ──
    per_period_bt.warmup_bars = min(per_period_bt.warmup_bars, len(oos_df) // 4)
    trades, eq = run_backtest(strategy, oos_df, per_period_bt)
    result.oos_report = compute_metrics(trades, eq, len(oos_df))
    fr = apply_filters(strategy, result.oos_report,
                       min_pf=min_pf * 0.8, min_sharpe=min_sharpe * 0.6,
                       max_dd=max_dd * 1.3, min_trades=max(3, min_trades // 3))
    result.passed_oos = fr.passed
    result.survived = result.passed_oos

    return result
