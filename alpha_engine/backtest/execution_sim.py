"""
Execution simulator for realistic order fill modeling.

Models partial fills, price impact, latency, and fill probability
to produce realistic execution results in backtesting.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class FillResult:
    filled_qty: float
    fill_price: float
    fill_cost: float
    slippage: float


class ExecutionSimulator:
    """
    Simulates realistic order execution with:
    - Fill probability based on volume participation
    - Price impact proportional to sqrt of participation
    - Random latency jitter
    """

    def __init__(
        self,
        fill_probability: float = 0.98,
        max_participation: float = 0.05,
        impact_bps: float = 5.0,
        latency_ms_mean: float = 10.0,
        seed: int = 42,
    ) -> None:
        self.fill_prob = fill_probability
        self.max_participation = max_participation
        self.impact_bps = impact_bps
        self.latency_mean = latency_ms_mean
        self._rng = np.random.RandomState(seed)

    def simulate_fill(
        self,
        target_qty: float,
        price: float,
        volume: float,
        side: int,
    ) -> FillResult:
        """
        Simulate execution of a single order.

        Parameters:
            target_qty: desired shares
            price: reference price at signal time
            volume: average daily volume
            side: +1 buy, -1 sell
        """
        max_shares = volume * self.max_participation
        feasible_qty = min(abs(target_qty), max_shares)

        if self._rng.random() > self.fill_prob:
            feasible_qty *= self._rng.uniform(0.5, 0.9)

        participation = feasible_qty / volume if volume > 0 else 0
        impact = self.impact_bps / 10_000 * np.sqrt(participation) * side
        fill_price = price * (1 + impact)

        latency_noise = self._rng.exponential(self.latency_mean / 1000)
        drift = self._rng.normal(0, 0.0001)
        fill_price *= (1 + drift * latency_noise)

        slippage = abs(fill_price - price) / price

        return FillResult(
            filled_qty=feasible_qty * np.sign(target_qty),
            fill_price=fill_price,
            fill_cost=abs(feasible_qty * fill_price),
            slippage=slippage,
        )

    def simulate_vectorized(
        self,
        target_positions: pd.Series,
        current_positions: pd.Series,
        prices: pd.Series,
        volumes: pd.Series,
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """
        Vectorized fill simulation for a single rebalance step.

        Returns: (filled_positions, fill_costs, slippage_series)
        """
        trades = target_positions - current_positions
        sides = np.sign(trades)

        max_trade = volumes * self.max_participation * prices
        capped_value = trades.abs().clip(upper=max_trade)
        fills = self._rng.binomial(1, self.fill_prob, size=len(trades))
        fill_mask = pd.Series(fills, index=trades.index).astype(float)
        partial = pd.Series(
            self._rng.uniform(0.5, 1.0, size=len(trades)), index=trades.index,
        )
        filled_value = capped_value * fill_mask * partial

        participation = filled_value / (volumes * prices).replace(0, np.nan).fillna(1e12)
        impact = self.impact_bps / 10_000 * np.sqrt(participation.clip(0, 1))
        slippage = impact * sides

        filled_positions = current_positions + filled_value * sides
        costs = filled_value * impact

        return filled_positions, costs, slippage.abs()
