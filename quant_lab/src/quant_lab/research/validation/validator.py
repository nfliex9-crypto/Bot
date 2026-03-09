from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .metrics import max_drawdown, profit_factor, sharpe, sortino
from .monte_carlo import monte_carlo_robustness
from .walk_forward import walk_forward_sharpe


@dataclass
class ValidationReport:
    sharpe: float
    sortino: float
    max_drawdown: float
    profit_factor: float
    walk_forward_consistency: float
    mc_sharpe_p10: float
    mc_mdd_p90: float


def validate_returns(returns: np.ndarray) -> ValidationReport:
    eq = np.cumprod(1 + returns)
    wf = walk_forward_sharpe(returns)
    mc = monte_carlo_robustness(returns)
    return ValidationReport(
        sharpe=sharpe(returns),
        sortino=sortino(returns),
        max_drawdown=max_drawdown(eq),
        profit_factor=profit_factor(returns),
        walk_forward_consistency=wf.consistency_score,
        mc_sharpe_p10=mc["mc_sharpe_p10"],
        mc_mdd_p90=mc["mc_mdd_p90"],
    )
