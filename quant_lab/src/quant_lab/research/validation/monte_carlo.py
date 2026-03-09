from __future__ import annotations

import numpy as np

from .metrics import max_drawdown, sharpe


def monte_carlo_robustness(
    returns: np.ndarray,
    n_paths: int = 200,
    block_size: int = 5,
    seed: int = 42,
) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    n = len(returns)
    if n < block_size:
        return {"mc_sharpe_p10": 0.0, "mc_mdd_p90": -1.0}

    sharpes: list[float] = []
    mdds: list[float] = []
    n_blocks = max(1, n // block_size)

    for _ in range(n_paths):
        idx = []
        for _ in range(n_blocks):
            start = int(rng.integers(0, n - block_size + 1))
            idx.extend(range(start, start + block_size))
        sample = returns[np.array(idx[:n])]
        equity = np.cumprod(1 + sample)
        sharpes.append(sharpe(sample))
        mdds.append(max_drawdown(equity))

    return {
        "mc_sharpe_p10": float(np.percentile(sharpes, 10)),
        "mc_mdd_p90": float(np.percentile(mdds, 90)),
    }
