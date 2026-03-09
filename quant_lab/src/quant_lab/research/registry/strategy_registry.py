from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

from quant_lab.common.types import StrategyThresholds


@dataclass
class StrategyRecord:
    name: str
    signal_col: str
    model_type: str
    entry: float
    exit: float
    sharpe: float
    sortino: float
    max_drawdown: float
    profit_factor: float
    turnover: float
    walk_forward_consistency: float
    mc_sharpe_p10: float
    mc_mdd_p90: float
    passed: bool = False


class StrategyRegistry:
    def __init__(self, path: str, thresholds: StrategyThresholds, truncate_on_start: bool = True) -> None:
        self.path = Path(path)
        self.thresholds = thresholds
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if truncate_on_start:
            self.path.write_text("", encoding="utf-8")

    def should_register(self, record: StrategyRecord) -> bool:
        return (
            record.sharpe >= self.thresholds.sharpe_min
            and record.max_drawdown >= self.thresholds.max_drawdown_min
            and record.profit_factor >= self.thresholds.profit_factor_min
            and record.walk_forward_consistency >= 0.5
            and record.mc_sharpe_p10 > 0.0
        )

    def register(self, record: StrategyRecord) -> StrategyRecord:
        record.passed = self.should_register(record)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record)) + "\n")
        return record
