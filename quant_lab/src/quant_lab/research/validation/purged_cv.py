from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Fold:
    train_idx: list[int]
    test_idx: list[int]


def purged_kfold_indices(n_samples: int, k: int = 5, embargo: int = 5) -> list[Fold]:
    if k <= 1 or n_samples <= k:
        raise ValueError("k must be > 1 and less than n_samples")
    fold_size = n_samples // k
    folds: list[Fold] = []

    for i in range(k):
        test_start = i * fold_size
        test_end = (i + 1) * fold_size if i < k - 1 else n_samples
        test_idx = list(range(test_start, test_end))

        train_left_end = max(0, test_start - embargo)
        train_right_start = min(n_samples, test_end + embargo)
        train_idx = list(range(0, train_left_end)) + list(range(train_right_start, n_samples))
        folds.append(Fold(train_idx=train_idx, test_idx=test_idx))
    return folds
