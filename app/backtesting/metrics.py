"""
Backtesting Metrics.

Computes the canonical set of performance metrics from a completed backtest run:
  - Win rate, profit factor
  - Max drawdown (absolute + percentage)
  - Sharpe ratio (annualised)
  - Sortino ratio
  - Calmar ratio
  - Expectancy per trade
  - MAE / MFE (Maximum Adverse / Favourable Excursion)
  - Trade duration statistics
"""
import math
import statistics
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class TradeStats:
    pnl: float
    entry_price: float
    exit_price: float
    direction: str
    duration_bars: int
    exit_reason: str      # stop_loss | take_profit | end_of_data | stop_loss_gap
    slippage_pips: float = 0.0
    spread_pips: float = 0.0
    mae: float = 0.0      # Maximum Adverse Excursion (worst intra-trade loss)
    mfe: float = 0.0      # Maximum Favourable Excursion (best intra-trade profit)


class BacktestMetrics:
    """
    Stateless metrics calculator for completed backtest runs.
    """

    def compute(
        self,
        trade_stats: List[TradeStats],
        initial_balance: float = 3000.0,
        trades_per_year: Optional[float] = None,
    ) -> dict:
        """
        Compute the full metrics suite from a list of TradeStats.
        """
        if not trade_stats:
            return {
                "summary": "no trades",
                "total_trades": 0,
            }

        pnls = [t.pnl for t in trade_stats]
        wins = [t for t in trade_stats if t.pnl > 0]
        losses = [t for t in trade_stats if t.pnl <= 0]

        total = len(trade_stats)
        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        total_pnl = sum(pnls)
        win_rate = len(wins) / total

        max_dd_abs, max_dd_pct, dd_series = self._drawdown(pnls, initial_balance)
        sharpe = self._sharpe(pnls, trades_per_year or total)
        sortino = self._sortino(pnls, trades_per_year or total)
        calmar = self._calmar(pnls, max_dd_pct, trades_per_year or total)
        consec_w, consec_l = self._streaks(pnls)
        avg_dur = sum(t.duration_bars for t in trade_stats) / total

        exit_dist: Dict[str, int] = {}
        for t in trade_stats:
            exit_dist[t.exit_reason] = exit_dist.get(t.exit_reason, 0) + 1

        avg_slippage = sum(t.slippage_pips for t in trade_stats) / total
        avg_spread = sum(t.spread_pips for t in trade_stats) / total
        total_commission = sum(getattr(t, "commission", 0) for t in trade_stats)

        avg_mae = sum(t.mae for t in trade_stats) / total
        avg_mfe = sum(t.mfe for t in trade_stats) / total

        return {
            "total_trades": total,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": round(win_rate, 4),
            "win_rate_pct": f"{win_rate * 100:.1f}%",
            "pnl": {
                "total": round(total_pnl, 2),
                "gross_profit": round(gross_profit, 2),
                "gross_loss": round(gross_loss, 2),
                "avg_win": round(gross_profit / max(len(wins), 1), 2),
                "avg_loss": round(-gross_loss / max(len(losses), 1), 2),
                "largest_win": round(max((t.pnl for t in wins), default=0.0), 2),
                "largest_loss": round(min((t.pnl for t in losses), default=0.0), 2),
                "expectancy": round(
                    win_rate * (gross_profit / max(len(wins), 1)) -
                    (1 - win_rate) * (gross_loss / max(len(losses), 1)),
                    2,
                ),
                "total_commission": round(total_commission, 2),
            },
            "risk": {
                "profit_factor": round(self._safe(gross_profit, gross_loss), 3),
                "max_drawdown_abs": round(max_dd_abs, 2),
                "max_drawdown_pct": round(max_dd_pct, 4),
                "max_drawdown_pct_str": f"{max_dd_pct * 100:.1f}%",
                "sharpe_ratio": round(sharpe, 3),
                "sortino_ratio": round(sortino, 3),
                "calmar_ratio": round(calmar, 3),
            },
            "streaks": {
                "max_consecutive_wins": consec_w,
                "max_consecutive_losses": consec_l,
            },
            "execution": {
                "avg_slippage_pips": round(avg_slippage, 3),
                "avg_spread_pips": round(avg_spread, 3),
                "avg_duration_bars": round(avg_dur, 1),
                "avg_mae": round(avg_mae, 2),
                "avg_mfe": round(avg_mfe, 2),
            },
            "exit_distribution": exit_dist,
            "final_balance": round(initial_balance + total_pnl, 2),
            "total_return_pct": round(total_pnl / initial_balance * 100, 2),
        }

    def equity_curve(
        self,
        trade_stats: List[TradeStats],
        initial_balance: float = 3000.0,
    ) -> List[dict]:
        equity = initial_balance
        peak = initial_balance
        curve = []
        for t in trade_stats:
            equity += t.pnl
            peak = max(peak, equity)
            dd = (peak - equity) / (peak + 1e-10)
            curve.append({
                "equity": round(equity, 2),
                "pnl": round(t.pnl, 2),
                "drawdown_pct": round(dd * 100, 2),
                "direction": t.direction,
                "exit_reason": t.exit_reason,
            })
        return curve

    # ── Private ────────────────────────────────────────────────────────────

    def _drawdown(
        self,
        pnls: List[float],
        initial: float,
    ) -> Tuple[float, float, List[float]]:
        equity = initial
        peak = initial
        max_dd = 0.0
        max_dd_pct = 0.0
        dd_series = []
        for p in pnls:
            equity += p
            peak = max(peak, equity)
            dd = peak - equity
            dd_pct = dd / (peak + 1e-10)
            dd_series.append(dd_pct)
            if dd > max_dd:
                max_dd = dd
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct
        return max_dd, max_dd_pct, dd_series

    def _sharpe(self, pnls: List[float], n: float) -> float:
        if len(pnls) < 2:
            return 0.0
        mean = statistics.mean(pnls)
        std = statistics.stdev(pnls)
        if std == 0:
            return 0.0
        trades_per_year = max(n, 1)
        return mean / std * math.sqrt(trades_per_year)

    def _sortino(self, pnls: List[float], n: float) -> float:
        if len(pnls) < 2:
            return 0.0
        mean = statistics.mean(pnls)
        downside = [p for p in pnls if p < 0]
        if not downside:
            return float("inf")
        ds_std = math.sqrt(sum(p ** 2 for p in downside) / len(downside))
        if ds_std == 0:
            return 0.0
        return mean / ds_std * math.sqrt(max(n, 1))

    def _calmar(self, pnls: List[float], max_dd_pct: float, n: float) -> float:
        if max_dd_pct <= 0 or len(pnls) < 2:
            return 0.0
        annual_return = sum(pnls) * (max(n, 1) / len(pnls))
        return self._safe(annual_return, max_dd_pct)

    def _streaks(self, pnls: List[float]) -> Tuple[int, int]:
        max_w = max_l = cur_w = cur_l = 0
        for p in pnls:
            if p > 0:
                cur_w += 1; cur_l = 0
                max_w = max(max_w, cur_w)
            else:
                cur_l += 1; cur_w = 0
                max_l = max(max_l, cur_l)
        return max_w, max_l

    def _safe(self, a: float, b: float) -> float:
        return a / b if b > 0 else float("inf")
