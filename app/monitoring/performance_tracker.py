"""
Performance Tracker.

Computes and caches performance metrics from closed trade history:
  - Win rate, profit factor, max drawdown, Sharpe ratio
  - Per-symbol, per-session, per-direction breakdown
  - Equity curve with drawdown overlay
  - Trade duration statistics
  - Rolling metrics (7-day, 30-day, all-time)
"""
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple

UTC = timezone.utc


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    return a / b if b != 0 else default


class PerformanceTracker:
    """
    Stateless performance calculator – takes a list of trade dicts
    and returns comprehensive metrics.
    """

    def compute(self, trades: List[dict], period_label: str = "all") -> dict:
        """
        Compute full performance metrics from a list of trade dicts.

        Each dict must have at minimum: pnl (float).
        Optional keys: symbol, direction, session, ai_confidence,
                       opened_at, closed_at, risk_reward_ratio.
        """
        if not trades:
            return {"period": period_label, "total_trades": 0}

        pnls = [float(t.get("pnl", 0)) for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        total_pnl = sum(pnls)
        win_rate = _safe_div(len(wins), len(pnls))
        profit_factor = _safe_div(gross_profit, gross_loss, float("inf"))

        max_dd, max_dd_pct = self._max_drawdown(pnls)
        sharpe = self._sharpe(pnls)
        sortino = self._sortino(pnls)
        calmar = self._calmar(pnls, max_dd_pct)
        avg_rr = self._avg_rr(trades)
        consec_wins, consec_losses = self._consecutive(pnls)
        duration_stats = self._duration_stats(trades)

        return {
            "period": period_label,
            "total_trades": len(trades),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": round(win_rate, 4),
            "win_rate_pct": f"{win_rate * 100:.1f}%",
            "pnl": {
                "total": round(total_pnl, 2),
                "gross_profit": round(gross_profit, 2),
                "gross_loss": round(gross_loss, 2),
                "avg_win": round(_safe_div(gross_profit, len(wins)), 2),
                "avg_loss": round(-_safe_div(gross_loss, len(losses)), 2),
                "largest_win": round(max(wins, default=0.0), 2),
                "largest_loss": round(min(losses, default=0.0), 2),
                "expectancy": round(
                    win_rate * _safe_div(gross_profit, len(wins))
                    + (1 - win_rate) * (-_safe_div(gross_loss, len(losses))),
                    2,
                ),
            },
            "risk": {
                "profit_factor": round(profit_factor, 3) if math.isfinite(profit_factor) else "∞",
                "max_drawdown": round(max_dd, 2),
                "max_drawdown_pct": f"{max_dd_pct * 100:.1f}%",
                "sharpe_ratio": round(sharpe, 3),
                "sortino_ratio": round(sortino, 3),
                "calmar_ratio": round(calmar, 3),
            },
            "streaks": {
                "max_consecutive_wins": consec_wins,
                "max_consecutive_losses": consec_losses,
            },
            "avg_rr": round(avg_rr, 2),
            "duration": duration_stats,
            "breakdown": {
                "by_symbol": self._by_key(trades, "symbol"),
                "by_direction": self._by_key(trades, "direction"),
                "by_session": self._by_key(trades, "session"),
            },
        }

    def equity_curve(
        self,
        trades: List[dict],
        initial_balance: float = 3000.0,
    ) -> List[dict]:
        """Build equity curve with running drawdown."""
        curve = []
        equity = initial_balance
        peak = initial_balance

        for t in sorted(trades, key=lambda x: x.get("closed_at") or ""):
            equity += float(t.get("pnl", 0))
            if equity > peak:
                peak = equity
            dd = (peak - equity) / (peak + 1e-10)
            curve.append({
                "date": t.get("closed_at"),
                "symbol": t.get("symbol", ""),
                "pnl": round(float(t.get("pnl", 0)), 2),
                "equity": round(equity, 2),
                "drawdown_pct": round(dd * 100, 2),
            })

        return curve

    def rolling_window(
        self,
        trades: List[dict],
        days: int,
    ) -> dict:
        """Compute metrics for trades in last `days` days."""
        cutoff = datetime.now(UTC) - timedelta(days=days)
        filtered = [
            t for t in trades
            if t.get("closed_at") and self._parse_dt(t["closed_at"]) >= cutoff
        ]
        return self.compute(filtered, period_label=f"{days}d")

    # ── Private helpers ──────────────────────────────────────────────────

    def _max_drawdown(self, pnls: List[float]) -> Tuple[float, float]:
        peak = 0.0
        equity = 0.0
        max_dd = 0.0
        peak_eq = 0.0
        for p in pnls:
            equity += p
            if equity > peak_eq:
                peak_eq = equity
            dd = peak_eq - equity
            if dd > max_dd:
                max_dd = dd
        max_dd_pct = max_dd / (peak_eq + 1e-10) if peak_eq > 0 else 0.0
        return max_dd, max_dd_pct

    def _sharpe(self, pnls: List[float], risk_free: float = 0.0) -> float:
        if len(pnls) < 2:
            return 0.0
        mean = statistics.mean(pnls)
        std = statistics.stdev(pnls)
        return _safe_div((mean - risk_free) * math.sqrt(252), std)

    def _sortino(self, pnls: List[float], risk_free: float = 0.0) -> float:
        if len(pnls) < 2:
            return 0.0
        mean = statistics.mean(pnls)
        downside = [p for p in pnls if p < risk_free]
        if not downside:
            return float("inf")
        downside_std = math.sqrt(sum((p - risk_free) ** 2 for p in downside) / len(downside))
        return _safe_div((mean - risk_free) * math.sqrt(252), downside_std)

    def _calmar(self, pnls: List[float], max_dd_pct: float) -> float:
        if len(pnls) < 2 or max_dd_pct <= 0:
            return 0.0
        annual_return = sum(pnls) * (252 / len(pnls))
        return _safe_div(annual_return, max_dd_pct)

    def _avg_rr(self, trades: List[dict]) -> float:
        rrs = [float(t["risk_reward_ratio"]) for t in trades
               if t.get("risk_reward_ratio") and float(t["risk_reward_ratio"]) > 0]
        return _safe_div(sum(rrs), len(rrs)) if rrs else 0.0

    def _consecutive(self, pnls: List[float]) -> Tuple[int, int]:
        max_w = max_l = cur_w = cur_l = 0
        for p in pnls:
            if p > 0:
                cur_w += 1; cur_l = 0
                max_w = max(max_w, cur_w)
            else:
                cur_l += 1; cur_w = 0
                max_l = max(max_l, cur_l)
        return max_w, max_l

    def _duration_stats(self, trades: List[dict]) -> dict:
        durations = []
        for t in trades:
            opened = self._parse_dt(t.get("opened_at"))
            closed = self._parse_dt(t.get("closed_at"))
            if opened and closed and closed > opened:
                durations.append((closed - opened).total_seconds() / 60)
        if not durations:
            return {}
        return {
            "avg_minutes": round(_safe_div(sum(durations), len(durations)), 1),
            "min_minutes": round(min(durations), 1),
            "max_minutes": round(max(durations), 1),
        }

    def _by_key(self, trades: List[dict], key: str) -> dict:
        groups: Dict[str, List[float]] = defaultdict(list)
        for t in trades:
            k = str(t.get(key) or "unknown")
            groups[k].append(float(t.get("pnl", 0)))
        result = {}
        for k, pnls in groups.items():
            wins = len([p for p in pnls if p > 0])
            result[k] = {
                "trades": len(pnls),
                "win_rate": round(_safe_div(wins, len(pnls)), 4),
                "pnl": round(sum(pnls), 2),
            }
        return result

    def _parse_dt(self, val) -> Optional[datetime]:
        if val is None:
            return None
        if isinstance(val, datetime):
            return val.replace(tzinfo=UTC) if val.tzinfo is None else val
        try:
            dt = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
            return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt
        except Exception:
            return None
