"""
High-Performance Vectorized Backtesting Engine.

Core simulation engine that converts strategy signals into realistic
P&L time series with transaction costs, slippage, and market impact.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

from ..config import BacktestConfig
from ..strategy.evaluator import StrategyEvaluator
from ..strategy.templates import StrategyTemplates
from ..strategy.universe import StrategySpec, StrategyType
from .costs import CostModel, DefaultCostModel
from .execution_sim import ExecutionSimulator
from .results import BacktestResult

logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    Vectorized backtesting engine.

    Converts raw position signals into equity curves by simulating
    daily P&L accounting with realistic frictions.
    """

    def __init__(
        self,
        config: Optional[BacktestConfig] = None,
        cost_model: Optional[CostModel] = None,
    ) -> None:
        self.config = config or BacktestConfig()
        self.cost_model = cost_model or DefaultCostModel(
            commission_bps=self.config.commission_bps,
            slippage_bps=self.config.slippage_bps,
        )
        self.templates = StrategyTemplates()
        self.exec_sim = ExecutionSimulator(fill_probability=self.config.fill_probability)

    def run(
        self,
        spec: StrategySpec,
        data: dict[str, pd.DataFrame],
        features: Optional[dict[str, pd.DataFrame]] = None,
    ) -> BacktestResult:
        """
        Backtest a single strategy specification against historical data.

        Returns a BacktestResult with returns, positions, and metrics.
        """
        signal = self._generate_signal(spec, data, features)
        if signal is None or signal.empty:
            logger.warning("No signal generated for %s", spec.name)
            return BacktestResult(strategy_id=spec.strategy_id, strategy_name=spec.name)

        primary_symbol = spec.symbols[0] if spec.symbols else list(data.keys())[0]
        prices = data[primary_symbol]["close"]
        volumes = data[primary_symbol]["volume"]

        common_idx = signal.index.intersection(prices.index)
        signal = signal.loc[common_idx]
        prices = prices.loc[common_idx]
        volumes = volumes.loc[common_idx]

        positions = self._signal_to_positions(signal, spec)
        returns = self._compute_returns(positions, prices, volumes)

        equity = self.config.initial_capital * (1 + returns).cumprod()

        result = BacktestResult(
            strategy_id=spec.strategy_id,
            strategy_name=spec.name,
            returns=returns,
            positions=positions,
            equity_curve=equity,
            costs=self._last_costs if hasattr(self, "_last_costs") else pd.Series(dtype=float),
            gross_returns=self._last_gross if hasattr(self, "_last_gross") else returns,
            metadata={"spec": spec.to_dict()},
        )
        result.compute_metrics()
        return result

    def run_batch(
        self,
        specs: list[StrategySpec],
        data: dict[str, pd.DataFrame],
        features: Optional[dict[str, pd.DataFrame]] = None,
        n_workers: int = 1,
    ) -> list[BacktestResult]:
        """Backtest multiple strategies. Serial by default, parallel with n_workers > 1."""
        results = []
        for i, spec in enumerate(specs):
            try:
                result = self.run(spec, data, features)
                results.append(result)
                if (i + 1) % 100 == 0:
                    logger.info("Backtested %d / %d strategies", i + 1, len(specs))
            except Exception as e:
                logger.error("Backtest failed for %s: %s", spec.name, e)
        return results

    def _generate_signal(
        self,
        spec: StrategySpec,
        data: dict[str, pd.DataFrame],
        features: Optional[dict[str, pd.DataFrame]],
    ) -> Optional[pd.Series]:
        """Dispatch to the appropriate template based on strategy type."""
        primary = spec.symbols[0] if spec.symbols else list(data.keys())[0]
        df = data.get(primary)
        if df is None:
            return None

        p = spec.parameters
        stype = spec.strategy_type

        if stype == StrategyType.MOMENTUM:
            return self.templates.momentum_crossover(
                df["close"],
                fast_window=p.get("fast_window", 10),
                slow_window=p.get("slow_window", 50),
                smoothing=p.get("smoothing", 3),
            )

        elif stype == StrategyType.MEAN_REVERSION:
            return self.templates.mean_reversion_zscore(
                df["close"],
                lookback=p.get("lookback", 21),
                entry_z=p.get("entry_z", 2.0),
                exit_z=p.get("exit_z", 0.5),
            )

        elif stype == StrategyType.BREAKOUT:
            return self.templates.breakout(
                df["high"], df["low"], df["close"],
                lookback=p.get("lookback", 20),
                atr_mult=p.get("atr_mult", 1.5),
            )

        elif stype == StrategyType.VOLATILITY:
            returns = df["close"].pct_change()
            return self.templates.volatility_regime_switch(
                returns,
                vol_window=p.get("vol_window", 21),
                regime_threshold=p.get("regime_threshold", 0.5),
            )

        elif stype == StrategyType.STAT_ARB:
            if len(spec.symbols) < 2:
                return None
            a_close = data[spec.symbols[0]]["close"]
            b_close = data[spec.symbols[1]]["close"]
            return self.templates.statistical_arbitrage(
                a_close, b_close,
                lookback=p.get("lookback", 63),
                entry_z=p.get("entry_z", 2.0),
            )

        elif stype == StrategyType.CROSS_ASSET:
            returns_matrix = pd.DataFrame(
                {sym: data[sym]["close"].pct_change() for sym in spec.symbols if sym in data}
            ).dropna()
            signals = self.templates.cross_asset_momentum(
                returns_matrix,
                lookback=p.get("lookback", 21),
                top_n=p.get("top_n", 3),
                bottom_n=p.get("bottom_n", 3),
            )
            return signals.mean(axis=1) if not signals.empty else None

        elif stype == StrategyType.FACTOR_COMBO:
            if features and primary in features:
                return self.templates.factor_combination(
                    features[primary],
                    weights=p.get("weights", {}),
                )
            return None

        elif stype == StrategyType.ML_ENSEMBLE:
            if features and primary in features:
                fwd_ret = df["close"].pct_change(5).shift(-5)
                return self.templates.ml_signal(
                    features[primary],
                    fwd_ret,
                    train_window=p.get("train_window", 252),
                    retrain_freq=p.get("retrain_freq", 21),
                )
            return None

        elif stype == StrategyType.REGIME_SWITCH:
            from ..features.regime import RegimeFeatures
            regime = RegimeFeatures.volatility_regime(df["close"].pct_change())
            return self.templates.regime_switching(
                df["close"], df["close"].pct_change(), regime,
                strategies=p.get("strategies", {}),
                params=p.get("params", {}),
            )

        return None

    def _signal_to_positions(self, signal: pd.Series, spec: StrategySpec) -> pd.Series:
        """Convert raw signal to position sizes respecting constraints."""
        positions = signal * spec.leverage

        max_pos = self.config.max_position_pct / spec.leverage if spec.leverage > 0 else self.config.max_position_pct
        positions = positions.clip(-max_pos, max_pos)

        if not spec.long_short:
            positions = positions.clip(lower=0)

        return positions

    def _compute_returns(
        self,
        positions: pd.Series,
        prices: pd.Series,
        volumes: pd.Series,
    ) -> pd.Series:
        """Compute net-of-cost returns from positions and prices."""
        price_returns = prices.pct_change()
        gross_returns = positions.shift(1) * price_returns

        trade_values = positions.diff().abs() * prices
        sides = positions.diff().apply(np.sign)

        costs = self.cost_model.vectorized_costs(
            trade_values, prices, volumes, sides,
        ) if isinstance(self.cost_model, DefaultCostModel) else trade_values * 0

        cost_impact = costs / (self.config.initial_capital * (1 + gross_returns.fillna(0)).cumprod())
        cost_impact = cost_impact.fillna(0).clip(0, 0.01)

        net_returns = gross_returns - cost_impact

        self._last_costs = costs
        self._last_gross = gross_returns

        return net_returns.fillna(0)
