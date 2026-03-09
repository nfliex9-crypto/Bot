"""
Kill Switch — emergency shutdown mechanism.

Monitors real-time conditions and triggers immediate position
liquidation when critical thresholds are breached.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class KillSwitchReason(Enum):
    DRAWDOWN = "max_drawdown_breached"
    DAILY_LOSS = "max_daily_loss_breached"
    CONSECUTIVE_LOSSES = "consecutive_loss_limit"
    MANUAL = "manual_activation"
    CONNECTIVITY = "connectivity_lost"
    ANOMALY = "anomaly_detected"
    VOLATILITY_SPIKE = "volatility_spike"


@dataclass
class KillSwitchEvent:
    timestamp: float = 0.0
    reason: KillSwitchReason = KillSwitchReason.MANUAL
    details: str = ""
    positions_at_trigger: dict[str, float] = field(default_factory=dict)
    nav_at_trigger: float = 0.0


class KillSwitch:
    """
    Emergency shutdown controller.

    When triggered, immediately flags all positions for liquidation
    and notifies registered callbacks.
    """

    def __init__(
        self,
        max_drawdown: float = 0.05,
        max_daily_loss: float = 0.03,
        max_consecutive_losses: int = 10,
        volatility_spike_mult: float = 5.0,
    ) -> None:
        self.max_drawdown = max_drawdown
        self.max_daily_loss = max_daily_loss
        self.max_consecutive_losses = max_consecutive_losses
        self.vol_spike_mult = volatility_spike_mult

        self._is_triggered = False
        self._events: list[KillSwitchEvent] = []
        self._callbacks: list[Callable[[KillSwitchEvent], None]] = []
        self._baseline_volatility: float = 0.0

    @property
    def is_triggered(self) -> bool:
        return self._is_triggered

    @property
    def events(self) -> list[KillSwitchEvent]:
        return list(self._events)

    def register_callback(self, callback: Callable[[KillSwitchEvent], None]) -> None:
        self._callbacks.append(callback)

    def set_baseline_volatility(self, vol: float) -> None:
        self._baseline_volatility = vol

    def check(
        self,
        current_drawdown: float,
        daily_return: float,
        consecutive_losses: int,
        current_volatility: float = 0.0,
        positions: Optional[dict[str, float]] = None,
        nav: float = 0.0,
    ) -> bool:
        """
        Evaluate all kill-switch conditions.
        Returns True if triggered (trading should stop).
        """
        if self._is_triggered:
            return True

        reason: Optional[KillSwitchReason] = None
        details = ""

        if current_drawdown >= self.max_drawdown:
            reason = KillSwitchReason.DRAWDOWN
            details = f"Drawdown {current_drawdown:.2%} >= {self.max_drawdown:.2%}"

        elif daily_return <= -self.max_daily_loss:
            reason = KillSwitchReason.DAILY_LOSS
            details = f"Daily loss {daily_return:.2%} >= {self.max_daily_loss:.2%}"

        elif consecutive_losses >= self.max_consecutive_losses:
            reason = KillSwitchReason.CONSECUTIVE_LOSSES
            details = f"Consecutive losses: {consecutive_losses}"

        elif (self._baseline_volatility > 0 and current_volatility > 0
              and current_volatility > self._baseline_volatility * self.vol_spike_mult):
            reason = KillSwitchReason.VOLATILITY_SPIKE
            details = f"Vol spike: {current_volatility:.4f} vs baseline {self._baseline_volatility:.4f}"

        if reason is not None:
            self._trigger(reason, details, positions or {}, nav)
            return True

        return False

    def trigger_manual(self, reason: str = "Manual kill switch") -> None:
        self._trigger(KillSwitchReason.MANUAL, reason, {}, 0.0)

    def reset(self) -> None:
        """Reset kill switch to allow trading to resume."""
        self._is_triggered = False
        logger.warning("Kill switch reset — trading can resume")

    def _trigger(
        self,
        reason: KillSwitchReason,
        details: str,
        positions: dict[str, float],
        nav: float,
    ) -> None:
        self._is_triggered = True
        event = KillSwitchEvent(
            timestamp=time.time(),
            reason=reason,
            details=details,
            positions_at_trigger=positions,
            nav_at_trigger=nav,
        )
        self._events.append(event)

        logger.critical("KILL SWITCH TRIGGERED: %s — %s", reason.value, details)

        for cb in self._callbacks:
            try:
                cb(event)
            except Exception as e:
                logger.error("Kill switch callback failed: %s", e)
