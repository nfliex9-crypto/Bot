"""
Strategy Generation Engine.

Automatically generates thousands of candidate strategies by
combining parameterized templates across parameter grids,
feature subsets, asset universes, and regime conditions.
"""

from __future__ import annotations

import itertools
import logging
from typing import Optional

import numpy as np
import pandas as pd

from ..config import StrategyConfig
from .templates import StrategyTemplates
from .universe import StrategySpec, StrategyType, StrategyUniverse

logger = logging.getLogger(__name__)


class StrategyGenerator:
    """
    Produces a universe of candidate strategies through systematic
    parameter sweeps and combinatorial composition.
    """

    def __init__(self, config: Optional[StrategyConfig] = None) -> None:
        self.config = config or StrategyConfig()
        self.templates = StrategyTemplates()
        self.universe = StrategyUniverse()

    def generate_all(
        self,
        symbols: list[str],
        feature_names: list[str],
    ) -> StrategyUniverse:
        """Generate the full strategy universe across all template types."""
        generators = [
            self._gen_momentum,
            self._gen_mean_reversion,
            self._gen_breakout,
            self._gen_volatility_regime,
            self._gen_stat_arb,
            self._gen_cross_asset,
            self._gen_factor_combo,
            self._gen_ml_ensemble,
            self._gen_regime_switching,
        ]

        for gen_fn in generators:
            try:
                specs = gen_fn(symbols, feature_names)
                added = self.universe.add_batch(specs)
                logger.info("%s: generated %d, added %d unique", gen_fn.__name__, len(specs), added)
            except Exception as e:
                logger.error("%s failed: %s", gen_fn.__name__, e)

        logger.info("Total strategies in universe: %d", self.universe.size)
        logger.info("Universe breakdown: %s", self.universe.summary())
        return self.universe

    def _gen_momentum(self, symbols: list[str], features: list[str]) -> list[StrategySpec]:
        specs = []
        fast_windows = [5, 10, 15, 20]
        slow_windows = [30, 50, 100, 200]
        holdings = [5, 10, 21]

        for fast, slow, hp in itertools.product(fast_windows, slow_windows, holdings):
            if fast >= slow:
                continue
            specs.append(StrategySpec(
                name=f"mom_{fast}_{slow}_h{hp}",
                strategy_type=StrategyType.MOMENTUM,
                symbols=symbols,
                parameters={"fast_window": fast, "slow_window": slow, "smoothing": 3},
                holding_period=hp,
                description=f"Momentum crossover fast={fast} slow={slow}",
            ))
        return specs

    def _gen_mean_reversion(self, symbols: list[str], features: list[str]) -> list[StrategySpec]:
        specs = []
        lookbacks = [10, 15, 21, 42, 63]
        entry_zs = [1.5, 2.0, 2.5, 3.0]
        holdings = [3, 5, 10]

        for lb, ez, hp in itertools.product(lookbacks, entry_zs, holdings):
            specs.append(StrategySpec(
                name=f"mr_z{ez}_{lb}_h{hp}",
                strategy_type=StrategyType.MEAN_REVERSION,
                symbols=symbols,
                parameters={"lookback": lb, "entry_z": ez, "exit_z": 0.5},
                holding_period=hp,
                description=f"Mean reversion z-score lookback={lb} entry={ez}",
            ))
        return specs

    def _gen_breakout(self, symbols: list[str], features: list[str]) -> list[StrategySpec]:
        specs = []
        lookbacks = [10, 20, 40, 60]
        atr_mults = [1.0, 1.5, 2.0, 2.5]
        holdings = [5, 10, 21]

        for lb, am, hp in itertools.product(lookbacks, atr_mults, holdings):
            specs.append(StrategySpec(
                name=f"brk_{lb}_atr{am}_h{hp}",
                strategy_type=StrategyType.BREAKOUT,
                symbols=symbols,
                parameters={"lookback": lb, "atr_mult": am},
                holding_period=hp,
                description=f"Breakout lookback={lb} ATR mult={am}",
            ))
        return specs

    def _gen_volatility_regime(self, symbols: list[str], features: list[str]) -> list[StrategySpec]:
        specs = []
        vol_windows = [10, 21, 42]
        thresholds = [0.3, 0.5, 0.7]
        holdings = [5, 10, 21]

        for vw, th, hp in itertools.product(vol_windows, thresholds, holdings):
            specs.append(StrategySpec(
                name=f"volreg_{vw}_t{th}_h{hp}",
                strategy_type=StrategyType.VOLATILITY,
                symbols=symbols,
                parameters={"vol_window": vw, "regime_threshold": th},
                holding_period=hp,
                description=f"Volatility regime switch vol_w={vw} thresh={th}",
            ))
        return specs

    def _gen_stat_arb(self, symbols: list[str], features: list[str]) -> list[StrategySpec]:
        specs = []
        if len(symbols) < 2:
            return specs

        lookbacks = [42, 63, 126]
        entry_zs = [1.5, 2.0, 2.5]

        pairs = list(itertools.combinations(symbols[:10], 2))
        for (a, b), lb, ez in itertools.product(pairs, lookbacks, entry_zs):
            specs.append(StrategySpec(
                name=f"sarb_{a}_{b}_{lb}_z{ez}",
                strategy_type=StrategyType.STAT_ARB,
                symbols=[a, b],
                parameters={"lookback": lb, "entry_z": ez},
                holding_period=10,
                long_short=True,
                description=f"Stat arb {a}/{b} lookback={lb}",
            ))
        return specs

    def _gen_cross_asset(self, symbols: list[str], features: list[str]) -> list[StrategySpec]:
        specs = []
        lookbacks = [10, 21, 42, 63]
        top_ns = [2, 3, 5]

        for lb, tn in itertools.product(lookbacks, top_ns):
            specs.append(StrategySpec(
                name=f"xasset_mom_{lb}_top{tn}",
                strategy_type=StrategyType.CROSS_ASSET,
                symbols=symbols,
                parameters={"lookback": lb, "top_n": tn, "bottom_n": tn},
                holding_period=lb,
                long_short=True,
                description=f"Cross-asset momentum lookback={lb} top/bottom={tn}",
            ))
        return specs

    def _gen_factor_combo(self, symbols: list[str], features: list[str]) -> list[StrategySpec]:
        specs = []
        rng = np.random.RandomState(42)

        n_combos = min(500, self.config.n_candidates // 5)
        available = [f for f in features if any(
            k in f for k in ["mom_", "zscore_", "vol_ratio", "mr_score", "rank_"]
        )]
        if not available:
            available = features[:20]

        for i in range(n_combos):
            n_feats = rng.randint(2, min(6, len(available) + 1))
            chosen = list(rng.choice(available, size=n_feats, replace=False))
            weights = {f: float(rng.uniform(-1, 1)) for f in chosen}

            specs.append(StrategySpec(
                name=f"factor_combo_{i}",
                strategy_type=StrategyType.FACTOR_COMBO,
                symbols=symbols,
                features_used=chosen,
                parameters={"weights": weights},
                holding_period=rng.choice([5, 10, 21]),
                description=f"Factor combination of {len(chosen)} features",
            ))
        return specs

    def _gen_ml_ensemble(self, symbols: list[str], features: list[str]) -> list[StrategySpec]:
        specs = []
        train_windows = [126, 252, 504]
        retrain_freqs = [21, 63]

        for tw, rf in itertools.product(train_windows, retrain_freqs):
            specs.append(StrategySpec(
                name=f"ml_gbm_{tw}_{rf}",
                strategy_type=StrategyType.ML_ENSEMBLE,
                symbols=symbols,
                features_used=features[:30],
                parameters={"train_window": tw, "retrain_freq": rf},
                holding_period=5,
                description=f"ML GBM train={tw} retrain={rf}",
            ))
        return specs

    def _gen_regime_switching(self, symbols: list[str], features: list[str]) -> list[StrategySpec]:
        specs = []
        combos = [
            {0: "mean_reversion", 1: "momentum", 2: "breakout"},
            {0: "mean_reversion", 1: "mean_reversion", 2: "momentum"},
            {0: "momentum", 1: "breakout", 2: "mean_reversion"},
        ]
        for i, regime_map in enumerate(combos):
            specs.append(StrategySpec(
                name=f"regime_switch_{i}",
                strategy_type=StrategyType.REGIME_SWITCH,
                symbols=symbols,
                parameters={
                    "strategies": regime_map,
                    "params": {
                        "momentum": {"fast_window": 10, "slow_window": 50},
                        "mean_reversion": {"lookback": 21, "entry_z": 2.0},
                        "breakout": {"lookback": 20, "atr_mult": 1.5},
                    },
                },
                holding_period=10,
                description=f"Regime-switching combo {i}",
            ))
        return specs
