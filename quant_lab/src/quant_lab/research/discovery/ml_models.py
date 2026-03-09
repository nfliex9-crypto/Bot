from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression


def train_logit_classifier(x: np.ndarray, y: np.ndarray) -> LogisticRegression:
    model = LogisticRegression(max_iter=500)
    model.fit(x, y)
    return model
