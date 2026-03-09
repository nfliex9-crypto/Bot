from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExecutionStats:
    submitted: int = 0
    filled: int = 0
    rejected: int = 0
    avg_latency_ms: float = 0.0
