"""
Strategy specification and universe management.

Each candidate strategy is represented as a StrategySpec — a serializable
description of signal logic, parameters, and metadata that can be
evaluated by the backtesting and validation engines.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class StrategyType(Enum):
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    STAT_ARB = "statistical_arbitrage"
    VOLATILITY = "volatility_regime"
    CROSS_ASSET = "cross_asset"
    FACTOR_COMBO = "factor_combination"
    ML_ENSEMBLE = "ml_ensemble"
    REGIME_SWITCH = "regime_switching"


@dataclass
class StrategySpec:
    """Immutable specification for a candidate strategy."""
    strategy_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    name: str = ""
    strategy_type: StrategyType = StrategyType.MOMENTUM
    symbols: list[str] = field(default_factory=list)
    features_used: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    holding_period: int = 5
    rebalance_freq: str = "daily"
    long_short: bool = True
    leverage: float = 1.0
    description: str = ""

    @property
    def fingerprint(self) -> str:
        """Deterministic hash for deduplication."""
        def _sanitize(obj: Any) -> Any:
            import numpy as np
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, dict):
                return {k: _sanitize(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [_sanitize(v) for v in obj]
            return obj

        payload = json.dumps(_sanitize({
            "type": self.strategy_type.value,
            "params": self.parameters,
            "features": sorted(self.features_used),
            "holding": self.holding_period,
        }), sort_keys=True)
        return hashlib.md5(payload.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "strategy_type": self.strategy_type.value,
            "symbols": self.symbols,
            "features_used": self.features_used,
            "parameters": self.parameters,
            "holding_period": self.holding_period,
            "rebalance_freq": self.rebalance_freq,
            "long_short": self.long_short,
            "leverage": self.leverage,
            "description": self.description,
            "fingerprint": self.fingerprint,
        }


class StrategyUniverse:
    """Manages the collection of candidate strategies with deduplication."""

    def __init__(self) -> None:
        self._strategies: dict[str, StrategySpec] = {}
        self._fingerprints: set[str] = set()

    def add(self, spec: StrategySpec) -> bool:
        """Add strategy if not a duplicate. Returns True if added."""
        fp = spec.fingerprint
        if fp in self._fingerprints:
            return False
        self._strategies[spec.strategy_id] = spec
        self._fingerprints.add(fp)
        return True

    def add_batch(self, specs: list[StrategySpec]) -> int:
        return sum(self.add(s) for s in specs)

    def get(self, strategy_id: str) -> Optional[StrategySpec]:
        return self._strategies.get(strategy_id)

    def all(self) -> list[StrategySpec]:
        return list(self._strategies.values())

    def filter_by_type(self, stype: StrategyType) -> list[StrategySpec]:
        return [s for s in self._strategies.values() if s.strategy_type == stype]

    def remove(self, strategy_id: str) -> None:
        spec = self._strategies.pop(strategy_id, None)
        if spec:
            self._fingerprints.discard(spec.fingerprint)

    @property
    def size(self) -> int:
        return len(self._strategies)

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for s in self._strategies.values():
            key = s.strategy_type.value
            counts[key] = counts.get(key, 0) + 1
        return counts
