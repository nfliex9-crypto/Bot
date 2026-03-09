"""
Strategy Evaluator — computes performance metrics from signal returns.

Provides all standard quantitative metrics used in institutional
strategy evaluation and ranking.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class PerformanceMetrics:
    """Complete performance profile for a strategy."""
    total_return: float = 0.0
    annualized_return: float = 0.0
    annualized_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration_days: int = 0
    profit_factor: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    payoff_ratio: float = 0.0
    n_trades: int = 0
    avg_holding_period: float = 0.0
    skewness: float = 0.0
    kurtosis: float = 0.0
    var_95: float = 0.0
    cvar_95: float = 0.0
    turnover: float = 0.0
    hit_rate_monthly: float = 0.0

    def passes_minimum(
        self,
        min_sharpe: float = 1.5,
        min_sortino: float = 2.0,
        max_drawdown: float = 0.15,
        min_profit_factor: float = 1.5,
        min_trades: int = 100,
    ) -> bool:
        return (
            self.sharpe_ratio >= min_sharpe
            and self.sortino_ratio >= min_sortino
            and self.max_drawdown <= max_drawdown
            and self.profit_factor >= min_profit_factor
            and self.n_trades >= min_trades
        )

    def to_dict(self) -> dict[str, float]:
        return {
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "annualized_volatility": self.annualized_volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_duration_days": self.max_drawdown_duration_days,
            "profit_factor": self.profit_factor,
            "win_rate": self.win_rate,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "payoff_ratio": self.payoff_ratio,
            "n_trades": self.n_trades,
            "skewness": self.skewness,
            "kurtosis": self.kurtosis,
            "var_95": self.var_95,
            "cvar_95": self.cvar_95,
            "turnover": self.turnover,
            "hit_rate_monthly": self.hit_rate_monthly,
        }


class StrategyEvaluator:
    """Compute institutional-grade performance metrics from returns."""

    @staticmethod
    def evaluate(
        returns: pd.Series,
        positions: Optional[pd.Series] = None,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252,
    ) -> PerformanceMetrics:
        if returns.empty or returns.std() == 0:
            return PerformanceMetrics()

        n = len(returns)
        total_ret = (1 + returns).prod() - 1
        ann_factor = periods_per_year
        ann_ret = (1 + total_ret) ** (ann_factor / n) - 1
        ann_vol = returns.std() * np.sqrt(ann_factor)

        excess = returns - risk_free_rate / ann_factor
        sharpe = excess.mean() / returns.std() * np.sqrt(ann_factor) if returns.std() > 0 else 0.0

        downside = returns[returns < 0]
        downside_std = downside.std() if len(downside) > 0 else np.nan
        sortino = (excess.mean() / downside_std * np.sqrt(ann_factor)) if (downside_std and downside_std > 0) else 0.0

        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        max_dd = abs(drawdown.min())

        dd_duration = 0
        max_dd_dur = 0
        for dd_val in drawdown:
            if dd_val < 0:
                dd_duration += 1
                max_dd_dur = max(max_dd_dur, dd_duration)
            else:
                dd_duration = 0

        calmar = ann_ret / max_dd if max_dd > 0 else 0.0

        wins = returns[returns > 0]
        losses = returns[returns < 0]
        gross_profit = wins.sum() if len(wins) > 0 else 0.0
        gross_loss = abs(losses.sum()) if len(losses) > 0 else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
        win_rate = len(wins) / n if n > 0 else 0.0
        avg_win = wins.mean() if len(wins) > 0 else 0.0
        avg_loss = losses.mean() if len(losses) > 0 else 0.0
        payoff = abs(avg_win / avg_loss) if avg_loss != 0 else float("inf")

        n_trades = 0
        if positions is not None:
            pos_changes = positions.diff().abs()
            n_trades = int((pos_changes > 0).sum())
            turnover = pos_changes.mean() * ann_factor if len(pos_changes) > 0 else 0.0
        else:
            signal_changes = (returns != 0).astype(int).diff().abs()
            n_trades = int(signal_changes.sum()) // 2 + 1
            turnover = 0.0

        var_95 = returns.quantile(0.05)
        cvar_95 = returns[returns <= var_95].mean() if (returns <= var_95).any() else var_95

        monthly = returns.resample("ME").sum() if hasattr(returns.index, "freq") or isinstance(returns.index, pd.DatetimeIndex) else returns
        try:
            monthly_grouped = returns.groupby(pd.Grouper(freq="ME")).sum()
            hit_monthly = (monthly_grouped > 0).mean()
        except Exception:
            hit_monthly = win_rate

        return PerformanceMetrics(
            total_return=total_ret,
            annualized_return=ann_ret,
            annualized_volatility=ann_vol,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            max_drawdown=max_dd,
            max_drawdown_duration_days=max_dd_dur,
            profit_factor=min(profit_factor, 100.0),
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            payoff_ratio=min(payoff, 100.0),
            n_trades=n_trades,
            skewness=returns.skew(),
            kurtosis=returns.kurt(),
            var_95=var_95,
            cvar_95=cvar_95,
            turnover=turnover,
            hit_rate_monthly=hit_monthly,
        )

    @staticmethod
    def rolling_sharpe(returns: pd.Series, window: int = 63) -> pd.Series:
        mean = returns.rolling(window).mean()
        std = returns.rolling(window).std().replace(0, np.nan)
        return (mean / std) * np.sqrt(252)

    @staticmethod
    def drawdown_series(returns: pd.Series) -> pd.Series:
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        return (cumulative - running_max) / running_max
