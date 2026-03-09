"""
Risk Management Engine — top-level orchestrator.

Integrates exposure limits, drawdown control, kill switch,
position sizing, and volatility targeting into a unified
risk management framework.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from ..config import RiskConfig
from .drawdown import DrawdownController, DrawdownState
from .kill_switch import KillSwitch
from .limits import ExposureLimits, ExposureSnapshot

logger = logging.getLogger(__name__)


@dataclass
class RiskState:
    """Complete risk state snapshot."""
    timestamp: float = 0.0
    nav: float = 0.0
    drawdown: DrawdownState = field(default_factory=DrawdownState)
    exposure: ExposureSnapshot = field(default_factory=ExposureSnapshot)
    kill_switch_active: bool = False
    position_scale: float = 1.0
    var_1d_99: float = 0.0
    expected_shortfall: float = 0.0
    is_compliant: bool = True
    violations: list[str] = field(default_factory=list)


class RiskManager:
    """
    Institutional risk management engine.

    Orchestrates all risk controls and produces compliant position targets.
    """

    def __init__(self, config: Optional[RiskConfig] = None) -> None:
        self.config = config or RiskConfig()
        self.limits = ExposureLimits(self.config)
        self.drawdown = DrawdownController(self.config)
        self.kill_switch = KillSwitch(
            max_drawdown=self.config.kill_switch_drawdown,
            max_daily_loss=self.config.kill_switch_daily_loss,
            max_consecutive_losses=self.config.kill_switch_consecutive_losses,
        )
        self._return_history: list[float] = []

    def evaluate(
        self,
        positions: dict[str, float],
        nav: float,
        daily_return: float = 0.0,
    ) -> RiskState:
        """
        Evaluate current risk state and produce position scaling recommendations.
        """
        dd_state = self.drawdown.update(nav)
        exp_state = self.limits.snapshot(positions, nav)
        is_compliant, violations = self.limits.check(positions, nav)

        self._return_history.append(daily_return)

        ks_triggered = self.kill_switch.check(
            current_drawdown=dd_state.current_drawdown,
            daily_return=daily_return,
            consecutive_losses=dd_state.consecutive_losses,
            positions=positions,
            nav=nav,
        )

        position_scale = dd_state.scale_factor
        if ks_triggered:
            position_scale = 0.0

        var_99 = self._compute_var(self.config.var_confidence)
        es = self._compute_expected_shortfall(self.config.var_confidence)

        return RiskState(
            nav=nav,
            drawdown=dd_state,
            exposure=exp_state,
            kill_switch_active=ks_triggered,
            position_scale=position_scale,
            var_1d_99=var_99,
            expected_shortfall=es,
            is_compliant=is_compliant and not ks_triggered,
            violations=violations,
        )

    def apply_risk_controls(
        self,
        target_positions: dict[str, float],
        nav: float,
        daily_return: float = 0.0,
    ) -> dict[str, float]:
        """
        Apply all risk controls to target positions and return
        risk-adjusted positions.
        """
        risk_state = self.evaluate(target_positions, nav, daily_return)

        if risk_state.kill_switch_active:
            logger.critical("Kill switch active — liquidating all positions")
            return {k: 0.0 for k in target_positions}

        scaled = {k: v * risk_state.position_scale for k, v in target_positions.items()}
        compliant = self.limits.scale_to_limits(scaled, nav)

        compliant = self._apply_volatility_target(compliant, nav)

        return compliant

    def size_position(
        self,
        symbol: str,
        signal_strength: float,
        price: float,
        volatility: float,
        nav: float,
    ) -> float:
        """
        Compute optimal position size for a single asset.

        Uses volatility-adjusted sizing with risk budget allocation.
        """
        max_risk_per_position = self.config.max_position_size_pct * nav
        vol_target = self.config.volatility_target

        if volatility <= 0:
            return 0.0

        notional = vol_target / volatility * abs(signal_strength) * nav
        notional = min(notional, max_risk_per_position)
        shares = notional / price if price > 0 else 0
        return shares * np.sign(signal_strength)

    def _apply_volatility_target(
        self, positions: dict[str, float], nav: float,
    ) -> dict[str, float]:
        """Scale portfolio to target volatility."""
        if len(self._return_history) < self.config.volatility_lookback:
            return positions

        recent = np.array(self._return_history[-self.config.volatility_lookback:])
        realized_vol = recent.std() * np.sqrt(252)

        if realized_vol <= 0:
            return positions

        vol_scale = self.config.volatility_target / realized_vol
        vol_scale = np.clip(vol_scale, 0.25, 2.0)

        return {k: v * vol_scale for k, v in positions.items()}

    def _compute_var(self, confidence: float) -> float:
        if len(self._return_history) < 30:
            return 0.0
        returns = np.array(self._return_history)
        return abs(np.percentile(returns, (1 - confidence) * 100))

    def _compute_expected_shortfall(self, confidence: float) -> float:
        if len(self._return_history) < 30:
            return 0.0
        returns = np.array(self._return_history)
        var = np.percentile(returns, (1 - confidence) * 100)
        tail = returns[returns <= var]
        return abs(tail.mean()) if len(tail) > 0 else abs(var)

    def stress_test(
        self,
        positions: dict[str, float],
        nav: float,
        scenarios: Optional[dict[str, dict[str, float]]] = None,
    ) -> dict[str, float]:
        """
        Run stress tests on current positions.

        scenarios: {scenario_name: {asset: shock_pct}}
        Returns: {scenario_name: portfolio_loss_pct}
        """
        if scenarios is None:
            scenarios = {
                "equity_crash_20pct": {"default": -0.20},
                "rate_shock_5pct": {"default": -0.05},
                "vol_spike_3x": {"default": -0.15},
                "liquidity_crisis": {"default": -0.10},
            }

        results = {}
        for name, shocks in scenarios.items():
            total_loss = 0.0
            for sym, pos_val in positions.items():
                shock = shocks.get(sym, shocks.get("default", -0.10))
                total_loss += pos_val * shock
            results[name] = total_loss / nav if nav > 0 else 0

        return results
