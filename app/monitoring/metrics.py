"""
Metrics Collector.

Tracks runtime metrics for the trading system using both in-memory
accumulators and Prometheus counters/gauges/histograms.

Tracked metrics:
  - Trade execution: latency, slippage, spread at entry
  - P&L: running total, per-symbol, per-session
  - Risk: current drawdown, session trade count
  - AI: confidence distribution, prediction counts
  - System: scan rate, errors, uptime
"""
import time
import threading
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Dict, List, Optional, Deque
from dataclasses import dataclass, field

from prometheus_client import (
    Counter, Gauge, Histogram, Summary,
    REGISTRY, CollectorRegistry,
)

UTC = timezone.utc


# ── Prometheus instruments ─────────────────────────────────────────────────

TRADES_TOTAL = Counter(
    "trading_bot_trades_total",
    "Total trades placed",
    ["symbol", "direction", "market", "mode"],
)
TRADES_CLOSED = Counter(
    "trading_bot_trades_closed_total",
    "Total trades closed",
    ["symbol", "outcome"],  # outcome: win | loss
)
PNL_GAUGE = Gauge(
    "trading_bot_pnl_total",
    "Cumulative P&L in account currency",
)
DRAWDOWN_GAUGE = Gauge(
    "trading_bot_drawdown_current",
    "Current drawdown (0–1)",
)
WIN_RATE_GAUGE = Gauge(
    "trading_bot_win_rate",
    "Running win rate (0–1)",
)
PROFIT_FACTOR_GAUGE = Gauge(
    "trading_bot_profit_factor",
    "Running profit factor",
)
SESSION_TRADES_GAUGE = Gauge(
    "trading_bot_session_trades",
    "Trades taken in current session",
)
AI_CONFIDENCE_HIST = Histogram(
    "trading_bot_ai_confidence",
    "AI confidence score distribution",
    buckets=[0.5, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.0],
)
TRADE_LATENCY_HIST = Histogram(
    "trading_bot_trade_latency_seconds",
    "Time from signal to order fill (seconds)",
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
)
SLIPPAGE_HIST = Histogram(
    "trading_bot_slippage_pips",
    "Slippage in pips",
    buckets=[0, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0],
)
SPREAD_HIST = Histogram(
    "trading_bot_spread_pips",
    "Spread at entry in pips",
    buckets=[0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0],
)
SCAN_COUNTER = Counter(
    "trading_bot_scans_total",
    "Total market scans performed",
)
SIGNALS_TOTAL = Counter(
    "trading_bot_signals_total",
    "Total signals generated",
    ["symbol", "status"],  # status: executed | rejected | expired
)
ERRORS_TOTAL = Counter(
    "trading_bot_errors_total",
    "Total errors",
    ["component"],
)
BALANCE_GAUGE = Gauge(
    "trading_bot_account_balance",
    "Current account balance",
)


@dataclass
class TradeRecord:
    trade_id: int
    symbol: str
    direction: str
    entry_price: float
    exit_price: Optional[float] = None
    pnl: float = 0.0
    latency_ms: float = 0.0
    slippage_pips: float = 0.0
    spread_pips: float = 0.0
    ai_confidence: float = 0.0
    opened_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    closed_at: Optional[datetime] = None


class MetricsCollector:
    """
    Thread-safe, singleton metrics collector.
    Aggregates in-memory stats and drives Prometheus instrumentation.
    """

    _instance: Optional["MetricsCollector"] = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._lock = threading.Lock()
        self._start_time = datetime.now(UTC)

        # Running trade records (last 1000)
        self._trades: Deque[TradeRecord] = deque(maxlen=1000)
        self._open_trades: Dict[int, TradeRecord] = {}

        # Running P&L
        self._total_pnl: float = 0.0
        self._peak_balance: float = 0.0
        self._current_balance: float = 0.0

        # Win/loss counters
        self._wins: int = 0
        self._losses: int = 0
        self._gross_profit: float = 0.0
        self._gross_loss: float = 0.0

        # Latency / slippage accumulators
        self._latencies: Deque[float] = deque(maxlen=500)
        self._slippages: Deque[float] = deque(maxlen=500)
        self._spreads: Deque[float] = deque(maxlen=500)
        self._confidences: Deque[float] = deque(maxlen=500)

        # Per-symbol stats
        self._symbol_stats: Dict[str, Dict] = defaultdict(lambda: {
            "trades": 0, "wins": 0, "pnl": 0.0
        })

        # Scan / error counters
        self._scan_count: int = 0
        self._error_count: int = 0
        self._signal_count: int = 0

    # ── Trade lifecycle ──────────────────────────────────────────────────

    def record_trade_open(
        self,
        trade_id: int,
        symbol: str,
        direction: str,
        entry_price: float,
        intended_price: float,
        spread_pips: float = 0.0,
        ai_confidence: float = 0.0,
        market: str = "forex",
        mode: str = "paper",
        latency_ms: float = 0.0,
    ):
        pip_size = 0.01 if symbol.endswith("JPY") else (1.0 if "USDT" in symbol else 0.0001)
        slippage = abs(entry_price - intended_price) / pip_size if pip_size > 0 else 0.0

        record = TradeRecord(
            trade_id=trade_id,
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            latency_ms=latency_ms,
            slippage_pips=slippage,
            spread_pips=spread_pips,
            ai_confidence=ai_confidence,
        )

        with self._lock:
            self._open_trades[trade_id] = record
            self._latencies.append(latency_ms)
            self._slippages.append(slippage)
            self._spreads.append(spread_pips)
            self._confidences.append(ai_confidence)

        TRADES_TOTAL.labels(symbol=symbol, direction=direction, market=market, mode=mode).inc()
        if latency_ms > 0:
            TRADE_LATENCY_HIST.observe(latency_ms / 1000.0)
        SLIPPAGE_HIST.observe(slippage)
        SPREAD_HIST.observe(spread_pips)
        if ai_confidence > 0:
            AI_CONFIDENCE_HIST.observe(ai_confidence)

    def record_trade_close(
        self,
        trade_id: int,
        exit_price: float,
        pnl: float,
    ):
        with self._lock:
            record = self._open_trades.pop(trade_id, None)
            if record:
                record.exit_price = exit_price
                record.pnl = pnl
                record.closed_at = datetime.now(UTC)
                self._trades.append(record)

            self._total_pnl += pnl
            if pnl > 0:
                self._wins += 1
                self._gross_profit += pnl
            else:
                self._losses += 1
                self._gross_loss += abs(pnl)

            sym = record.symbol if record else "unknown"
            self._symbol_stats[sym]["trades"] += 1
            self._symbol_stats[sym]["pnl"] += pnl
            if pnl > 0:
                self._symbol_stats[sym]["wins"] += 1

        outcome = "win" if pnl > 0 else "loss"
        sym = record.symbol if record else "unknown"
        TRADES_CLOSED.labels(symbol=sym, outcome=outcome).inc()
        PNL_GAUGE.set(self._total_pnl)
        self._update_derived_gauges()

    def record_balance(self, balance: float):
        with self._lock:
            self._current_balance = balance
            if balance > self._peak_balance:
                self._peak_balance = balance
            dd = (self._peak_balance - balance) / (self._peak_balance + 1e-10) \
                if self._peak_balance > 0 else 0.0
        BALANCE_GAUGE.set(balance)
        DRAWDOWN_GAUGE.set(dd)

    def record_scan(self):
        with self._lock:
            self._scan_count += 1
        SCAN_COUNTER.inc()

    def record_signal(self, symbol: str, status: str):
        with self._lock:
            self._signal_count += 1
        SIGNALS_TOTAL.labels(symbol=symbol, status=status).inc()

    def record_error(self, component: str):
        with self._lock:
            self._error_count += 1
        ERRORS_TOTAL.labels(component=component).inc()

    def record_session_trades(self, count: int):
        SESSION_TRADES_GAUGE.set(count)

    def _update_derived_gauges(self):
        total = self._wins + self._losses
        if total > 0:
            WIN_RATE_GAUGE.set(self._wins / total)
        pf = self._gross_profit / (self._gross_loss + 1e-10)
        PROFIT_FACTOR_GAUGE.set(pf)

    # ── Snapshot / export ────────────────────────────────────────────────

    def snapshot(self) -> dict:
        """Return a JSON-serializable snapshot of all metrics."""
        with self._lock:
            total = self._wins + self._losses
            win_rate = self._wins / total if total > 0 else 0.0
            profit_factor = self._gross_profit / (self._gross_loss + 1e-10)
            avg_latency = sum(self._latencies) / len(self._latencies) if self._latencies else 0.0
            avg_slippage = sum(self._slippages) / len(self._slippages) if self._slippages else 0.0
            avg_spread = sum(self._spreads) / len(self._spreads) if self._spreads else 0.0
            avg_conf = sum(self._confidences) / len(self._confidences) if self._confidences else 0.0
            dd = (self._peak_balance - self._current_balance) / (self._peak_balance + 1e-10) \
                if self._peak_balance > 0 else 0.0
            uptime_s = (datetime.now(UTC) - self._start_time).total_seconds()

        return {
            "uptime_seconds": round(uptime_s),
            "pnl": {"total": round(self._total_pnl, 2), "gross_profit": round(self._gross_profit, 2),
                    "gross_loss": round(self._gross_loss, 2)},
            "trades": {"total": total, "wins": self._wins, "losses": self._losses,
                       "open": len(self._open_trades)},
            "win_rate": round(win_rate, 4),
            "profit_factor": round(profit_factor, 3),
            "drawdown": {"current": round(dd, 4), "peak_balance": round(self._peak_balance, 2),
                         "current_balance": round(self._current_balance, 2)},
            "execution": {"avg_latency_ms": round(avg_latency, 2), "avg_slippage_pips": round(avg_slippage, 3),
                          "avg_spread_pips": round(avg_spread, 3)},
            "ai": {"avg_confidence": round(avg_conf, 4), "signals_generated": self._signal_count},
            "system": {"scans": self._scan_count, "errors": self._error_count},
            "per_symbol": {
                sym: {
                    "trades": v["trades"],
                    "win_rate": round(v["wins"] / v["trades"], 4) if v["trades"] > 0 else 0.0,
                    "pnl": round(v["pnl"], 2),
                }
                for sym, v in self._symbol_stats.items()
            },
        }

    def recent_trades(self, n: int = 20) -> List[dict]:
        with self._lock:
            recs = list(self._trades)[-n:]
        return [
            {
                "trade_id": r.trade_id,
                "symbol": r.symbol,
                "direction": r.direction,
                "entry": r.entry_price,
                "exit": r.exit_price,
                "pnl": round(r.pnl, 2),
                "latency_ms": round(r.latency_ms, 1),
                "slippage_pips": round(r.slippage_pips, 2),
                "spread_pips": round(r.spread_pips, 2),
                "ai_confidence": round(r.ai_confidence, 4),
                "opened_at": r.opened_at.isoformat(),
                "closed_at": r.closed_at.isoformat() if r.closed_at else None,
            }
            for r in recs
        ]


def get_metrics() -> MetricsCollector:
    """Return the singleton MetricsCollector instance."""
    return MetricsCollector()
