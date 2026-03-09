"""
Strategy configuration data structures.

Each strategy is represented as a StrategyConfig with declarative
entry/exit conditions that can be evaluated vectorially on DataFrames.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class Condition:
    """
    A single boolean condition evaluated per bar.

    left/right are either column names (str) referencing a DataFrame column,
    or numeric constants (int/float).

    Supported ops: ">", "<", ">=", "<=", "==",
                   "cross_above", "cross_below"
    """
    left: Any
    op: str
    right: Any


@dataclass
class StrategyConfig:
    name: str
    family: str
    params: Dict[str, Any]
    long_entry: List[Condition]
    short_entry: List[Condition]
    long_exit: List[Condition] = field(default_factory=list)
    short_exit: List[Condition] = field(default_factory=list)
    sl_atr_mult: float = 1.5
    tp_rr: float = 2.0
    risk_pct: float = 0.01
    complexity: int = 0
    description: str = ""

    def __post_init__(self):
        if self.complexity == 0:
            self.complexity = (
                len(self.long_entry)
                + len(self.short_entry)
                + len(self.long_exit)
                + len(self.short_exit)
            )
