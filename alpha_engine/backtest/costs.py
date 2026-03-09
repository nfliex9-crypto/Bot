"""
Transaction cost modeling.

Realistic cost models including commissions, slippage, market impact,
and borrow costs for institutional-grade backtesting.
"""

from __future__ import annotations

import abc

import numpy as np
import pandas as pd


class CostModel(abc.ABC):
    """Abstract transaction cost model."""

    @abc.abstractmethod
    def total_cost(
        self,
        trade_value: float,
        price: float,
        volume: float,
        side: int,
    ) -> float:
        """Return total cost in dollar terms for a trade."""
        ...


class DefaultCostModel(CostModel):
    """
    Realistic institutional cost model.

    Components:
    1. Fixed commission (bps of trade value)
    2. Linear slippage (bps of trade value)
    3. Square-root market impact (Almgren-Chriss style)
    4. Borrow cost for short positions
    """

    def __init__(
        self,
        commission_bps: float = 2.0,
        slippage_bps: float = 1.0,
        impact_coefficient: float = 0.1,
        borrow_cost_bps: float = 50.0,
        daily_borrow: bool = True,
    ) -> None:
        self.commission_bps = commission_bps
        self.slippage_bps = slippage_bps
        self.impact_coeff = impact_coefficient
        self.borrow_bps = borrow_cost_bps
        self.daily_borrow = daily_borrow

    def total_cost(
        self,
        trade_value: float,
        price: float,
        volume: float,
        side: int,
    ) -> float:
        """
        Parameters:
            trade_value: absolute dollar value of the trade
            price: execution price
            volume: average daily volume in shares
            side: +1 for buy, -1 for sell/short
        """
        commission = trade_value * self.commission_bps / 10_000
        slippage = trade_value * self.slippage_bps / 10_000

        participation = trade_value / (price * volume) if (price * volume) > 0 else 0
        impact = self.impact_coeff * trade_value * np.sqrt(participation)

        borrow = 0.0
        if side < 0 and self.daily_borrow:
            borrow = trade_value * self.borrow_bps / 10_000 / 252

        return commission + slippage + impact + borrow

    def vectorized_costs(
        self,
        trade_values: pd.Series,
        prices: pd.Series,
        volumes: pd.Series,
        sides: pd.Series,
    ) -> pd.Series:
        """Vectorized cost computation for full backtest."""
        abs_trade = trade_values.abs()
        commission = abs_trade * self.commission_bps / 10_000
        slippage = abs_trade * self.slippage_bps / 10_000

        dollar_volume = prices * volumes
        participation = abs_trade / dollar_volume.replace(0, np.nan).fillna(1e12)
        impact = self.impact_coeff * abs_trade * np.sqrt(participation.clip(0, 1))

        borrow = pd.Series(0.0, index=trade_values.index)
        short_mask = sides < 0
        borrow[short_mask] = abs_trade[short_mask] * self.borrow_bps / 10_000 / 252

        return commission + slippage + impact + borrow
