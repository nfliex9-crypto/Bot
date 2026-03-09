"""
Risk Guards.

Additional execution-time risk protections beyond basic position sizing:

  SpreadFilter       – blocks execution when spread is too wide
  SlippageGuard      – rejects fills where slippage exceeds tolerance
  LatencyGuard       – aborts order if execution latency exceeds threshold
  DrawdownStop       – hard circuit breaker for daily/total drawdown
  TradeCooldown      – enforces a minimum wait between trades per symbol
  CompositeRiskGuard – wraps all guards and returns a single decision

These guards sit between signal generation and order placement.
They receive context (tick data, timing, account state) and return
a RiskDecision indicating whether to proceed.
"""
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple

from app.utils.logger import get_logger

logger = get_logger("risk_guards")

UTC = timezone.utc


@dataclass
class RiskDecision:
    allowed: bool
    reason: Optional[str] = None
    details: Optional[dict] = None


# ── Individual Guards ──────────────────────────────────────────────────────


class SpreadFilter:
    """
    Rejects trades when the spread is too wide relative to ATR.

    Wide spreads (e.g. during news, thin liquidity) increase cost
    and reduce win probability.
    """

    def __init__(
        self,
        max_spread_pips: float = 3.0,
        max_spread_atr_ratio: float = 0.30,  # spread ≤ 30 % of ATR
    ):
        self.max_spread_pips = max_spread_pips
        self.max_spread_atr_ratio = max_spread_atr_ratio

    def check(
        self,
        symbol: str,
        spread_pips: float,
        atr_pips: Optional[float] = None,
    ) -> RiskDecision:
        if spread_pips > self.max_spread_pips:
            return RiskDecision(
                allowed=False,
                reason="spread_too_wide",
                details={
                    "spread_pips": spread_pips,
                    "max_pips": self.max_spread_pips,
                    "symbol": symbol,
                },
            )

        if atr_pips and atr_pips > 0:
            ratio = spread_pips / atr_pips
            if ratio > self.max_spread_atr_ratio:
                return RiskDecision(
                    allowed=False,
                    reason="spread_atr_ratio_exceeded",
                    details={
                        "spread_pips": spread_pips,
                        "atr_pips": atr_pips,
                        "ratio": round(ratio, 3),
                        "max_ratio": self.max_spread_atr_ratio,
                    },
                )

        return RiskDecision(allowed=True)


class SlippageGuard:
    """
    Rejects fill if slippage exceeds tolerance.

    Call `verify_fill()` after receiving the broker's actual fill price
    to decide whether to immediately close a badly-slipped trade.
    """

    def __init__(
        self,
        max_slippage_pips: float = 2.0,
        auto_close_threshold_pips: float = 5.0,
    ):
        self.max_slippage_pips = max_slippage_pips
        self.auto_close_threshold = auto_close_threshold_pips

    def verify_fill(
        self,
        symbol: str,
        intended_price: float,
        actual_price: float,
        direction: str,
    ) -> RiskDecision:
        pip_size = 0.01 if symbol.endswith("JPY") else (1.0 if "USDT" in symbol else 0.0001)
        if direction == "long":
            slippage = (actual_price - intended_price) / pip_size
        else:
            slippage = (intended_price - actual_price) / pip_size

        slippage = max(slippage, 0.0)

        if slippage >= self.auto_close_threshold:
            logger.warning(
                f"EXCESSIVE SLIPPAGE on {symbol}: {slippage:.1f} pips — close immediately"
            )
            return RiskDecision(
                allowed=False,
                reason="excessive_slippage_close",
                details={"slippage_pips": round(slippage, 2), "auto_close": True},
            )

        if slippage > self.max_slippage_pips:
            logger.warning(
                f"HIGH SLIPPAGE on {symbol}: {slippage:.1f} pips > {self.max_slippage_pips}"
            )
            return RiskDecision(
                allowed=False,
                reason="slippage_exceeded",
                details={"slippage_pips": round(slippage, 2)},
            )

        return RiskDecision(
            allowed=True,
            details={"slippage_pips": round(slippage, 2)},
        )


class LatencyGuard:
    """
    Aborts order placement if broker latency is too high.

    High latency means the market may have moved significantly
    since signal generation — the entry price may be stale.
    """

    def __init__(
        self,
        max_latency_ms: float = 1000.0,      # 1 second
        warn_latency_ms: float = 500.0,
    ):
        self.max_latency_ms = max_latency_ms
        self.warn_latency_ms = warn_latency_ms

    def check(self, signal_time: datetime, now: Optional[datetime] = None) -> RiskDecision:
        if now is None:
            now = datetime.now(UTC)
        if signal_time.tzinfo is None:
            signal_time = signal_time.replace(tzinfo=UTC)

        latency_ms = (now - signal_time).total_seconds() * 1000

        if latency_ms > self.max_latency_ms:
            logger.warning(
                f"Trade aborted: signal latency {latency_ms:.0f}ms "
                f"> max {self.max_latency_ms:.0f}ms"
            )
            return RiskDecision(
                allowed=False,
                reason="latency_exceeded",
                details={"latency_ms": round(latency_ms, 1), "max_ms": self.max_latency_ms},
            )

        if latency_ms > self.warn_latency_ms:
            logger.warning(f"High latency warning: {latency_ms:.0f}ms")

        return RiskDecision(
            allowed=True,
            details={"latency_ms": round(latency_ms, 1)},
        )

    def measure(self, start: float) -> float:
        """Return elapsed milliseconds since `start` (from time.perf_counter())."""
        return (time.perf_counter() - start) * 1000


class DrawdownStop:
    """
    Hard circuit breaker.

    Halts all new trades when:
      - Intraday loss exceeds daily_stop_pct of starting equity
      - Total drawdown exceeds max_drawdown_pct
    """

    def __init__(
        self,
        max_drawdown_pct: float = 0.15,  # 15 % total
        daily_stop_pct: float = 0.05,    # 5 % intraday
    ):
        self.max_drawdown_pct = max_drawdown_pct
        self.daily_stop_pct = daily_stop_pct

        self._peak_balance: float = 0.0
        self._day_start_balance: float = 0.0
        self._tripped: bool = False
        self._trip_reason: Optional[str] = None

    def update(self, balance: float):
        if self._peak_balance == 0:
            self._peak_balance = balance
        if self._day_start_balance == 0:
            self._day_start_balance = balance
        self._peak_balance = max(self._peak_balance, balance)

    def reset_daily(self, current_balance: float):
        self._day_start_balance = current_balance
        self._tripped = False
        self._trip_reason = None

    def check(self, current_balance: float) -> RiskDecision:
        if self._tripped:
            return RiskDecision(
                allowed=False,
                reason=self._trip_reason,
                details={"circuit_breaker": "tripped"},
            )

        self.update(current_balance)

        # Total drawdown check
        total_dd = (self._peak_balance - current_balance) / (self._peak_balance + 1e-10)
        if total_dd >= self.max_drawdown_pct:
            self._tripped = True
            self._trip_reason = "max_drawdown_stop"
            logger.error(
                f"CIRCUIT BREAKER: max drawdown {total_dd:.1%} >= {self.max_drawdown_pct:.1%}"
            )
            return RiskDecision(
                allowed=False,
                reason="max_drawdown_stop",
                details={"drawdown_pct": round(total_dd, 4)},
            )

        # Daily loss check
        if self._day_start_balance > 0:
            daily_loss_pct = (self._day_start_balance - current_balance) / self._day_start_balance
            if daily_loss_pct >= self.daily_stop_pct:
                self._tripped = True
                self._trip_reason = "daily_stop_loss"
                logger.error(
                    f"CIRCUIT BREAKER: daily loss {daily_loss_pct:.1%} >= {self.daily_stop_pct:.1%}"
                )
                return RiskDecision(
                    allowed=False,
                    reason="daily_stop_loss",
                    details={"daily_loss_pct": round(daily_loss_pct, 4)},
                )

        return RiskDecision(
            allowed=True,
            details={
                "total_drawdown": round(total_dd, 4),
                "daily_loss": round(
                    (self._day_start_balance - current_balance) / (self._day_start_balance + 1e-10), 4
                ),
            },
        )

    @property
    def is_tripped(self) -> bool:
        return self._tripped


class TradeCooldown:
    """
    Enforces a minimum wait between consecutive trades on the same symbol.

    Prevents over-trading after a loss and avoids stacking multiple
    trades on correlated pairs within a short window.
    """

    def __init__(
        self,
        cooldown_minutes: int = 15,
        loss_cooldown_minutes: int = 30,
    ):
        self.cooldown_minutes = cooldown_minutes
        self.loss_cooldown_minutes = loss_cooldown_minutes
        self._last_trade: Dict[str, datetime] = {}
        self._last_was_loss: Dict[str, bool] = {}

    def record_trade(self, symbol: str, was_loss: bool = False):
        self._last_trade[symbol] = datetime.now(UTC)
        self._last_was_loss[symbol] = was_loss

    def check(self, symbol: str) -> RiskDecision:
        if symbol not in self._last_trade:
            return RiskDecision(allowed=True)

        last = self._last_trade[symbol]
        was_loss = self._last_was_loss.get(symbol, False)
        cooldown = self.loss_cooldown_minutes if was_loss else self.cooldown_minutes
        elapsed = (datetime.now(UTC) - last).total_seconds() / 60

        if elapsed < cooldown:
            remaining = round(cooldown - elapsed, 1)
            return RiskDecision(
                allowed=False,
                reason="trade_cooldown",
                details={
                    "symbol": symbol,
                    "cooldown_minutes": cooldown,
                    "remaining_minutes": remaining,
                    "after_loss": was_loss,
                },
            )

        return RiskDecision(allowed=True)


# ── Composite Guard ────────────────────────────────────────────────────────


class CompositeRiskGuard:
    """
    Runs all guards in sequence and returns the first rejection,
    or an aggregate ALLOWED decision if all pass.
    """

    def __init__(
        self,
        max_spread_pips: float = 3.0,
        max_slippage_pips: float = 2.0,
        max_latency_ms: float = 1000.0,
        max_drawdown_pct: float = 0.15,
        daily_stop_pct: float = 0.05,
        cooldown_minutes: int = 15,
        loss_cooldown_minutes: int = 30,
    ):
        self.spread_filter = SpreadFilter(max_spread_pips)
        self.slippage_guard = SlippageGuard(max_slippage_pips)
        self.latency_guard = LatencyGuard(max_latency_ms)
        self.drawdown_stop = DrawdownStop(max_drawdown_pct, daily_stop_pct)
        self.cooldown = TradeCooldown(cooldown_minutes, loss_cooldown_minutes)

    def pre_trade_check(
        self,
        symbol: str,
        spread_pips: float,
        atr_pips: Optional[float],
        signal_time: datetime,
        current_balance: float,
    ) -> RiskDecision:
        """
        Run all pre-trade guards. Call before placing an order.
        """
        checks = [
            ("drawdown_stop", self.drawdown_stop.check(current_balance)),
            ("spread_filter", self.spread_filter.check(symbol, spread_pips, atr_pips)),
            ("latency_guard", self.latency_guard.check(signal_time)),
            ("cooldown", self.cooldown.check(symbol)),
        ]
        for name, decision in checks:
            if not decision.allowed:
                logger.info(f"Pre-trade guard [{name}] blocked: {decision.reason}")
                return decision

        return RiskDecision(allowed=True)

    def post_fill_check(
        self,
        symbol: str,
        intended_price: float,
        actual_price: float,
        direction: str,
    ) -> RiskDecision:
        """Check actual fill vs intended price for excessive slippage."""
        return self.slippage_guard.verify_fill(
            symbol, intended_price, actual_price, direction
        )

    def record_trade_result(self, symbol: str, pnl: float):
        """Record outcome for cooldown logic."""
        self.cooldown.record_trade(symbol, was_loss=pnl <= 0)
        self.drawdown_stop.update(
            self.drawdown_stop._peak_balance + pnl
        )

    def update_balance(self, balance: float):
        self.drawdown_stop.update(balance)

    def reset_daily(self, balance: float):
        self.drawdown_stop.reset_daily(balance)

    def is_circuit_broken(self) -> bool:
        return self.drawdown_stop.is_tripped

    def status(self) -> dict:
        return {
            "circuit_breaker_tripped": self.drawdown_stop.is_tripped,
            "trip_reason": self.drawdown_stop._trip_reason,
            "max_spread_pips": self.spread_filter.max_spread_pips,
            "max_slippage_pips": self.slippage_guard.max_slippage_pips,
            "max_latency_ms": self.latency_guard.max_latency_ms,
            "max_drawdown_pct": self.drawdown_stop.max_drawdown_pct,
            "daily_stop_pct": self.drawdown_stop.daily_stop_pct,
            "cooldown_minutes": self.cooldown.cooldown_minutes,
        }
