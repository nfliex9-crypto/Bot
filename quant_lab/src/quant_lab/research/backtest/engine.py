from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import polars as pl

from .costs import transaction_costs
from .slippage import slippage_costs


@dataclass
class BacktestResult:
    strategy_name: str
    returns: np.ndarray
    equity_curve: np.ndarray
    turnover: float


class VectorizedBacktester:
    def __init__(self, fee_bps: float = 1.0, slippage_bps: float = 2.0) -> None:
        self.fee_bps = fee_bps
        self.slippage_bps = slippage_bps

    @staticmethod
    def _signal_to_position(signal: np.ndarray, entry: float, exit: float, model_type: str) -> np.ndarray:
        if model_type == "mean_reversion":
            pos = np.where(signal > entry, -1.0, np.where(signal < -entry, 1.0, 0.0))
        else:
            pos = np.where(signal > entry, 1.0, np.where(signal < -entry, -1.0, 0.0))
        pos[np.abs(signal) < exit] = 0.0
        return pos

    def run(self, df: pl.DataFrame, strategy_name: str, signal_col: str, model_type: str, entry: float, exit: float) -> BacktestResult:
        signal = np.nan_to_num(df[signal_col].to_numpy(), nan=0.0)
        rets = np.nan_to_num(df["ret_1"].to_numpy(), nan=0.0)
        vol = np.abs(rets)

        pos = self._signal_to_position(signal, entry, exit, model_type)
        pos_lag = np.roll(pos, 1)
        pos_lag[0] = 0.0

        gross = pos_lag * rets
        trades = np.diff(pos_lag, prepend=0.0)
        costs = transaction_costs(trades, self.fee_bps) + slippage_costs(trades, self.slippage_bps, vol)
        net = gross - costs

        equity = np.cumprod(1 + net)
        turnover = float(np.mean(np.abs(trades)))
        return BacktestResult(strategy_name=strategy_name, returns=net, equity_curve=equity, turnover=turnover)
