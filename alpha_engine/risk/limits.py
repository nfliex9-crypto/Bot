"""
Exposure limits enforcement for institutional risk management.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from ..config import RiskConfig

logger = logging.getLogger(__name__)


@dataclass
class ExposureSnapshot:
    """Current portfolio exposure state."""
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    long_exposure: float = 0.0
    short_exposure: float = 0.0
    max_position: float = 0.0
    max_sector_exposure: float = 0.0
    n_positions: int = 0


class ExposureLimits:
    """Enforce position and exposure limits at the portfolio level."""

    def __init__(self, config: RiskConfig) -> None:
        self.config = config

    def check(self, positions: dict[str, float], nav: float) -> tuple[bool, list[str]]:
        """
        Check if current positions satisfy all exposure limits.
        Returns (is_compliant, list_of_violations).
        """
        violations: list[str] = []
        if nav <= 0:
            return False, ["NAV is zero or negative"]

        pos_values = np.array(list(positions.values()))
        long_exp = pos_values[pos_values > 0].sum() / nav
        short_exp = abs(pos_values[pos_values < 0].sum()) / nav
        gross = long_exp + short_exp
        net = long_exp - short_exp

        if gross > self.config.max_gross_exposure:
            violations.append(
                f"Gross exposure {gross:.2f} > limit {self.config.max_gross_exposure:.2f}"
            )

        if abs(net) > self.config.max_net_exposure:
            violations.append(
                f"Net exposure {abs(net):.2f} > limit {self.config.max_net_exposure:.2f}"
            )

        for sym, val in positions.items():
            pct = abs(val) / nav
            if pct > self.config.position_limit_per_asset:
                violations.append(
                    f"Position {sym}: {pct:.2%} > limit {self.config.position_limit_per_asset:.2%}"
                )

        return len(violations) == 0, violations

    def scale_to_limits(self, positions: dict[str, float], nav: float) -> dict[str, float]:
        """Scale positions down proportionally to satisfy all limits."""
        if nav <= 0:
            return {k: 0.0 for k in positions}

        scaled = dict(positions)

        for sym in scaled:
            max_val = nav * self.config.position_limit_per_asset
            if abs(scaled[sym]) > max_val:
                scaled[sym] = np.sign(scaled[sym]) * max_val

        pos_values = np.array(list(scaled.values()))
        gross = np.abs(pos_values).sum() / nav
        if gross > self.config.max_gross_exposure:
            factor = self.config.max_gross_exposure / gross
            scaled = {k: v * factor for k, v in scaled.items()}

        return scaled

    def snapshot(self, positions: dict[str, float], nav: float) -> ExposureSnapshot:
        """Get current exposure state."""
        pos_values = np.array(list(positions.values())) if positions else np.array([0.0])
        return ExposureSnapshot(
            gross_exposure=np.abs(pos_values).sum() / max(nav, 1),
            net_exposure=pos_values.sum() / max(nav, 1),
            long_exposure=pos_values[pos_values > 0].sum() / max(nav, 1) if (pos_values > 0).any() else 0,
            short_exposure=abs(pos_values[pos_values < 0].sum()) / max(nav, 1) if (pos_values < 0).any() else 0,
            max_position=np.abs(pos_values).max() / max(nav, 1) if len(pos_values) > 0 else 0,
            n_positions=int((np.abs(pos_values) > 0).sum()),
        )
