from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .metrics import sharpe


@dataclass(frozen=True)
class WalkForwardResult:
    train_sharpes: list[float]
    test_sharpes: list[float]
    consistency_score: float


def walk_forward_sharpe(returns: np.ndarray, train_size: int = 252, test_size: int = 63) -> WalkForwardResult:
    n = len(returns)
    i = 0
    train_scores: list[float] = []
    test_scores: list[float] = []
    while i + train_size + test_size <= n:
        train = returns[i : i + train_size]
        test = returns[i + train_size : i + train_size + test_size]
        train_scores.append(sharpe(train))
        test_scores.append(sharpe(test))
        i += test_size

    if not test_scores:
        return WalkForwardResult([], [], 0.0)

    consistency = float(np.mean(np.array(test_scores) > 0))
    return WalkForwardResult(train_scores, test_scores, consistency)
