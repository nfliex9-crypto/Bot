from __future__ import annotations

import numpy as np

from quant_lab.research.validation.purged_cv import purged_kfold_indices
from quant_lab.research.validation.validator import validate_returns


def test_validate_returns_and_purged_cv():
    rng = np.random.default_rng(123)
    returns = rng.normal(0.001, 0.01, size=800)
    report = validate_returns(returns)
    assert isinstance(report.sharpe, float)
    assert report.max_drawdown <= 0.0

    folds = purged_kfold_indices(n_samples=500, k=5, embargo=10)
    assert len(folds) == 5
    assert len(folds[0].train_idx) > 0
