"""
Strategy filtering criteria.

Applies minimum quality thresholds to discard strategies that are
unlikely to be robust in live trading.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from app.discovery.metrics import PerformanceReport
from app.discovery.strategy_config import StrategyConfig

MIN_PROFIT_FACTOR = 1.5
MIN_SHARPE = 1.0
MAX_DRAWDOWN = 0.15
MIN_TRADES = 20


@dataclass
class FilterResult:
    strategy: StrategyConfig
    report: PerformanceReport
    passed: bool
    rejection_reasons: List[str]


def apply_filters(
    strategy: StrategyConfig,
    report: PerformanceReport,
    min_pf: float = MIN_PROFIT_FACTOR,
    min_sharpe: float = MIN_SHARPE,
    max_dd: float = MAX_DRAWDOWN,
    min_trades: int = MIN_TRADES,
) -> FilterResult:
    reasons: List[str] = []

    if report.total_trades < min_trades:
        reasons.append(f"trades={report.total_trades}<{min_trades}")
    if report.profit_factor < min_pf:
        reasons.append(f"PF={report.profit_factor:.2f}<{min_pf}")
    if report.sharpe_ratio < min_sharpe:
        reasons.append(f"Sharpe={report.sharpe_ratio:.2f}<{min_sharpe}")
    if report.max_drawdown > max_dd:
        reasons.append(f"DD={report.max_drawdown:.2%}>{max_dd:.0%}")

    return FilterResult(
        strategy=strategy,
        report=report,
        passed=len(reasons) == 0,
        rejection_reasons=reasons,
    )


def filter_batch(
    results: List[Tuple[StrategyConfig, PerformanceReport]],
    **kwargs,
) -> Tuple[List[FilterResult], List[FilterResult]]:
    """Split results into (passed, rejected) lists."""
    passed, rejected = [], []
    for strat, report in results:
        fr = apply_filters(strat, report, **kwargs)
        (passed if fr.passed else rejected).append(fr)
    return passed, rejected
