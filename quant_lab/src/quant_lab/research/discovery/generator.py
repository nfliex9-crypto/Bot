from __future__ import annotations

from dataclasses import dataclass
from itertools import product


@dataclass(frozen=True)
class StrategySpec:
    name: str
    signal_col: str
    model_type: str
    entry: float
    exit: float
    side: str


class StrategyGenerator:
    def __init__(self, factor_cols: list[str]) -> None:
        self.factor_cols = factor_cols

    def generate(self) -> list[StrategySpec]:
        specs: list[StrategySpec] = []
        entries = [0.005, 0.01, 0.02]
        exits = [0.0, 0.002]
        model_types = ["threshold", "mean_reversion", "momentum"]

        for col, model, entry, exit_ in product(self.factor_cols, model_types, entries, exits):
            specs.append(
                StrategySpec(
                    name=f"{model}_{col}_entry{entry}_exit{exit_}",
                    signal_col=col,
                    model_type=model,
                    entry=entry,
                    exit=exit_,
                    side="long_short",
                )
            )
        return specs
