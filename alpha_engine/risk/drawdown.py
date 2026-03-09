"""
Drawdown control and management.

Implements dynamic position scaling based on drawdown depth,
daily loss limits, and consecutive loss tracking.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from ..config import RiskConfig

logger = logging.getLogger(__name__)


@dataclass
class DrawdownState:
    """Current drawdown tracking state."""
    peak_nav: float = 0.0
    current_nav: float = 0.0
    current_drawdown: float = 0.0
    max_drawdown: float = 0.0
    daily_pnl: float = 0.0
    daily_loss_pct: float = 0.0
    consecutive_losses: int = 0
    days_in_drawdown: int = 0
    scale_factor: float = 1.0
    is_halted: bool = False
    halt_reason: str = ""


class DrawdownController:
    """
    Dynamic drawdown management with graduated position scaling.

    As drawdown deepens, positions are progressively reduced
    to limit further losses while preserving the ability to recover.
    """

    def __init__(self, config: RiskConfig) -> None:
        self.config = config
        self._peak_nav: float = 0.0
        self._prev_nav: float = 0.0
        self._consecutive_losses: int = 0
        self._days_in_drawdown: int = 0
        self._max_drawdown: float = 0.0
        self._daily_returns: list[float] = []

    def update(self, current_nav: float) -> DrawdownState:
        """
        Update drawdown state with current NAV and compute position scaling.

        Returns DrawdownState with the recommended scale_factor.
        """
        if self._peak_nav == 0:
            self._peak_nav = current_nav
            self._prev_nav = current_nav

        self._peak_nav = max(self._peak_nav, current_nav)
        current_dd = (self._peak_nav - current_nav) / self._peak_nav if self._peak_nav > 0 else 0
        self._max_drawdown = max(self._max_drawdown, current_dd)

        daily_ret = (current_nav - self._prev_nav) / self._prev_nav if self._prev_nav > 0 else 0
        self._daily_returns.append(daily_ret)
        self._prev_nav = current_nav

        if daily_ret < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

        if current_dd > 0:
            self._days_in_drawdown += 1
        else:
            self._days_in_drawdown = 0

        scale_factor = self._compute_scale(current_dd, daily_ret)
        halt_reason = self._check_halt(current_dd, daily_ret)

        state = DrawdownState(
            peak_nav=self._peak_nav,
            current_nav=current_nav,
            current_drawdown=current_dd,
            max_drawdown=self._max_drawdown,
            daily_pnl=daily_ret * self._prev_nav,
            daily_loss_pct=daily_ret,
            consecutive_losses=self._consecutive_losses,
            days_in_drawdown=self._days_in_drawdown,
            scale_factor=scale_factor,
            is_halted=bool(halt_reason),
            halt_reason=halt_reason,
        )

        if state.is_halted:
            logger.critical("TRADING HALTED: %s (DD=%.2f%%)", halt_reason, current_dd * 100)
        elif scale_factor < 1.0:
            logger.warning("Position scale reduced to %.0f%% (DD=%.2f%%)", scale_factor * 100, current_dd * 100)

        return state

    def _compute_scale(self, drawdown: float, daily_return: float) -> float:
        """
        Graduated position scaling based on drawdown depth.

        Scale linearly from 100% at 0% DD to 25% at max_portfolio_drawdown.
        """
        max_dd = self.config.max_portfolio_drawdown
        if max_dd <= 0:
            return 1.0

        dd_pct = drawdown / max_dd
        if dd_pct <= 0.5:
            return 1.0
        elif dd_pct <= 0.75:
            return 0.75
        elif dd_pct <= 0.9:
            return 0.5
        elif dd_pct < 1.0:
            return 0.25
        else:
            return 0.0

    def _check_halt(self, drawdown: float, daily_return: float) -> str:
        """Check if any halt condition is triggered."""
        if drawdown >= self.config.max_portfolio_drawdown:
            return f"Portfolio drawdown {drawdown:.2%} >= limit {self.config.max_portfolio_drawdown:.2%}"

        if abs(daily_return) >= self.config.max_daily_loss and daily_return < 0:
            return f"Daily loss {daily_return:.2%} >= limit {self.config.max_daily_loss:.2%}"

        if self._consecutive_losses >= self.config.kill_switch_consecutive_losses:
            return f"Consecutive losses: {self._consecutive_losses}"

        return ""

    def reset(self, new_peak: float | None = None) -> None:
        """Reset drawdown tracking, optionally with a new peak."""
        if new_peak is not None:
            self._peak_nav = new_peak
        self._consecutive_losses = 0
        self._days_in_drawdown = 0
        self._max_drawdown = 0.0
        self._daily_returns = []
