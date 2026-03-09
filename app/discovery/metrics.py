"""
Performance metrics for strategy evaluation.

All functions accept a list of trade dicts (each with at least 'pnl') and
an equity curve (list of floats).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Dict

import numpy as np


@dataclass
class PerformanceReport:
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    avg_r_multiple: float = 0.0
    trade_frequency: float = 0.0
    total_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    expectancy: float = 0.0
    total_bars: int = 0
    consistency: float = 0.0

    def passes_filters(
        self,
        min_pf: float = 1.5,
        min_sharpe: float = 1.0,
        max_dd: float = 0.15,
        min_trades: int = 20,
    ) -> bool:
        return (
            self.total_trades >= min_trades
            and self.profit_factor >= min_pf
            and self.sharpe_ratio >= min_sharpe
            and self.max_drawdown <= max_dd
        )

    def to_dict(self) -> dict:
        return {k: round(v, 6) if isinstance(v, float) else v
                for k, v in self.__dict__.items()}


def compute_metrics(
    trades: List[Dict],
    equity_curve: List[float],
    total_bars: int = 0,
    annual_factor: float = 252.0,
) -> PerformanceReport:
    """Compute full performance report from trade list and equity curve."""
    report = PerformanceReport()
    report.total_bars = total_bars

    if not trades:
        return report

    pnls = np.array([t.get("pnl", 0.0) for t in trades], dtype=float)
    r_multiples = np.array([t.get("r_multiple", 0.0) for t in trades], dtype=float)

    winners = pnls[pnls > 0]
    losers = pnls[pnls <= 0]

    report.total_trades = len(pnls)
    report.winning_trades = len(winners)
    report.losing_trades = len(losers)
    report.win_rate = len(winners) / len(pnls) if len(pnls) > 0 else 0.0
    report.total_pnl = float(pnls.sum())
    report.avg_win = float(winners.mean()) if len(winners) > 0 else 0.0
    report.avg_loss = float(losers.mean()) if len(losers) > 0 else 0.0

    gross_profit = float(winners.sum()) if len(winners) > 0 else 0.0
    gross_loss = abs(float(losers.sum())) if len(losers) > 0 else 0.0
    report.profit_factor = (
        gross_profit / gross_loss if gross_loss > 0 else 10.0
    )
    report.profit_factor = min(report.profit_factor, 10.0)

    report.avg_r_multiple = float(r_multiples.mean()) if len(r_multiples) > 0 else 0.0
    report.expectancy = float(pnls.mean()) if len(pnls) > 0 else 0.0

    if total_bars > 0:
        report.trade_frequency = report.total_trades / total_bars
    else:
        report.trade_frequency = 0.0

    # Sharpe ratio from equity curve returns
    curve = np.array(equity_curve, dtype=float)
    if len(curve) > 2:
        returns = np.diff(curve) / curve[:-1]
        returns = returns[np.isfinite(returns)]
        if len(returns) > 1 and np.std(returns) > 0:
            report.sharpe_ratio = float(
                np.mean(returns) / np.std(returns) * math.sqrt(annual_factor)
            )
        else:
            report.sharpe_ratio = 0.0
    else:
        report.sharpe_ratio = 0.0

    # Max drawdown
    if len(curve) > 1:
        peak = np.maximum.accumulate(curve)
        dd = (peak - curve) / np.where(peak > 0, peak, 1.0)
        report.max_drawdown = float(dd.max())
    else:
        report.max_drawdown = 0.0

    # Consistency: split trades into quarters and check profitability
    if len(pnls) >= 8:
        quarter = len(pnls) // 4
        quarters_profitable = sum(
            1 for i in range(4)
            if pnls[i * quarter: (i + 1) * quarter].sum() > 0
        )
        report.consistency = quarters_profitable / 4.0
    elif len(pnls) >= 4:
        half = len(pnls) // 2
        halves_profitable = sum(
            1 for i in range(2)
            if pnls[i * half: (i + 1) * half].sum() > 0
        )
        report.consistency = halves_profitable / 2.0
    else:
        report.consistency = 1.0 if report.total_pnl > 0 else 0.0

    return report
