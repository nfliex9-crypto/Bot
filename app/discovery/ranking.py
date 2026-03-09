"""
Strategy ranking with composite scoring.

Composite score formula (weights sum to 1.0):
    0.30 × normalised Sharpe ratio
  + 0.25 × normalised profit factor
  + 0.25 × normalised inverse max-drawdown
  + 0.20 × consistency across periods

A simplicity bonus penalises complex strategies: −0.02 per condition
beyond 4 total conditions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from app.discovery.metrics import PerformanceReport
from app.discovery.strategy_config import StrategyConfig
from app.discovery.validation import ValidationResult

W_SHARPE = 0.30
W_PF = 0.25
W_DD = 0.25
W_CONSISTENCY = 0.20
SIMPLICITY_PENALTY = 0.02
SIMPLICITY_THRESHOLD = 4


@dataclass
class RankedStrategy:
    strategy: StrategyConfig
    composite_score: float
    sharpe_score: float
    pf_score: float
    dd_score: float
    consistency_score: float
    simplicity_bonus: float
    train_report: PerformanceReport
    val_report: PerformanceReport
    oos_report: PerformanceReport


def _normalise(values: List[float]) -> List[float]:
    """Min-max normalise to [0, 1]."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    rng = hi - lo
    if rng == 0:
        return [0.5] * len(values)
    return [(v - lo) / rng for v in values]


def rank_strategies(results: List[ValidationResult]) -> List[RankedStrategy]:
    """
    Rank strategies that survived walk-forward validation.

    Uses the *out-of-sample* report as the primary metric source,
    cross-referenced with training and validation for consistency.
    """
    survived = [r for r in results if r.survived and r.oos_report is not None]
    if not survived:
        return []

    sharpes = [r.oos_report.sharpe_ratio for r in survived]
    pfs = [min(r.oos_report.profit_factor, 5.0) for r in survived]
    dds = [r.oos_report.max_drawdown for r in survived]

    norm_sharpe = _normalise(sharpes)
    norm_pf = _normalise(pfs)
    inv_dd = [1.0 - d for d in dds]
    norm_dd = _normalise(inv_dd)

    ranked: List[RankedStrategy] = []
    for idx, vr in enumerate(survived):
        avg_consistency = (
            (vr.train_report.consistency if vr.train_report else 0)
            + (vr.val_report.consistency if vr.val_report else 0)
            + (vr.oos_report.consistency if vr.oos_report else 0)
        ) / 3.0

        simplicity = max(0, vr.strategy.complexity - SIMPLICITY_THRESHOLD) * SIMPLICITY_PENALTY

        composite = (
            W_SHARPE * norm_sharpe[idx]
            + W_PF * norm_pf[idx]
            + W_DD * norm_dd[idx]
            + W_CONSISTENCY * avg_consistency
            - simplicity
        )

        ranked.append(RankedStrategy(
            strategy=vr.strategy,
            composite_score=round(composite, 6),
            sharpe_score=round(norm_sharpe[idx], 6),
            pf_score=round(norm_pf[idx], 6),
            dd_score=round(norm_dd[idx], 6),
            consistency_score=round(avg_consistency, 4),
            simplicity_bonus=round(-simplicity, 4),
            train_report=vr.train_report,
            val_report=vr.val_report,
            oos_report=vr.oos_report,
        ))

    ranked.sort(key=lambda r: r.composite_score, reverse=True)
    return ranked
