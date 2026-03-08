"""
Tests for the AI classifier and feature engineering.
"""

import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timedelta

from ai.feature_engine import extract_features
from ai.classifier import TradeClassifier


def _make_df(n=100, base=1.1):
    times = [datetime.utcnow() - timedelta(minutes=5 * (n - i)) for i in range(n)]
    data = []
    price = base
    for t in times:
        change = np.random.normal(0, 0.001)
        price += change
        o = price + np.random.normal(0, 0.0005)
        c = price + np.random.normal(0, 0.0005)
        h = max(o, c) + abs(np.random.normal(0, 0.0005))
        l = min(o, c) - abs(np.random.normal(0, 0.0005))
        v = np.random.randint(100, 5000)
        data.append({"timestamp": t, "open": o, "high": h, "low": l, "close": c, "volume": float(v)})
    return pd.DataFrame(data)


class TestFeatureEngine:
    def test_extract_features(self):
        h1 = _make_df(100)
        m15 = _make_df(100)
        m5 = _make_df(100)
        features = extract_features(h1, m15, m5)
        assert isinstance(features, dict)
        assert len(features) > 20
        assert all(isinstance(v, (int, float)) for v in features.values())

    def test_no_nan_in_features(self):
        h1 = _make_df(100)
        m15 = _make_df(100)
        m5 = _make_df(100)
        features = extract_features(h1, m15, m5)
        for k, v in features.items():
            assert not (isinstance(v, float) and np.isnan(v)), f"NaN found in {k}"


class TestClassifier:
    def test_untrained_returns_default(self):
        clf = TradeClassifier()
        clf.is_trained = False
        prob, conf = clf.predict({})
        assert prob == 0.5
        assert conf == 0.5

    def test_train_with_data(self):
        clf = TradeClassifier()
        clf._init_fresh()

        n = 50
        features = []
        for _ in range(n):
            features.append({
                "f1": np.random.randn(),
                "f2": np.random.randn(),
                "f3": np.random.randn(),
                "f4": np.random.randn(),
                "f5": np.random.randn(),
            })

        df = pd.DataFrame(features)
        labels = np.random.randint(0, 2, size=n)

        result = clf.train(df, labels)
        assert result["status"] == "trained"
        assert clf.is_trained is True

    def test_predict_after_training(self):
        clf = TradeClassifier()
        clf._init_fresh()

        n = 50
        features = [{"f1": np.random.randn(), "f2": np.random.randn()} for _ in range(n)]
        df = pd.DataFrame(features)
        labels = np.random.randint(0, 2, size=n)

        clf.train(df, labels)
        prob, conf = clf.predict({"f1": 0.5, "f2": -0.3})
        assert 0 <= prob <= 1
        assert 0 <= conf <= 1

    def test_score_signal(self):
        clf = TradeClassifier()
        h1 = _make_df(100)
        m15 = _make_df(100)
        m5 = _make_df(100)
        combined, ai_score = clf.score_signal(h1, m15, m5, 0.7)
        assert 0 <= combined <= 1
