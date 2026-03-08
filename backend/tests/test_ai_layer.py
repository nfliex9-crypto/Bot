"""Tests for the AI classifier and feature engineering."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone

from app.ai_layer.feature_engineering import FeatureEngineer
from app.ai_layer.classifier import TradeClassifier


def generate_test_data(n=300, seed=42):
    np.random.seed(seed)
    base_price = 1.1000
    timestamps = pd.date_range(end=datetime.now(timezone.utc), periods=n, freq="h")
    returns = np.random.normal(0.0001, 0.001, n)
    closes = base_price * np.exp(np.cumsum(returns))
    highs = closes * (1 + np.abs(np.random.normal(0, 0.0005, n)))
    lows = closes * (1 - np.abs(np.random.normal(0, 0.0005, n)))
    opens = np.roll(closes, 1)
    opens[0] = base_price
    volumes = np.random.randint(100, 10000, n).astype(float)

    return pd.DataFrame({
        "timestamp": timestamps,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })


class TestFeatureEngineer:
    def setup_method(self):
        self.fe = FeatureEngineer()

    def test_extract_features_shape(self):
        df = generate_test_data()
        features = self.fe.extract_features(df)
        assert len(features) == len(df)
        assert len(features.columns) == len(FeatureEngineer.FEATURE_COLUMNS)

    def test_extract_features_no_infinities(self):
        df = generate_test_data()
        features = self.fe.extract_features(df)
        assert not np.isinf(features.values).any()

    def test_extract_features_no_nans(self):
        df = generate_test_data()
        features = self.fe.extract_features(df)
        assert not features.isna().any().any()

    def test_insufficient_data(self):
        df = generate_test_data(n=10)
        features = self.fe.extract_features(df)
        assert features.empty

    def test_create_labels(self):
        df = generate_test_data()
        labels = self.fe.create_labels(df)
        assert len(labels) == len(df)
        valid = labels.dropna()
        assert set(valid.unique()).issubset({0, 1})

    def test_trade_features(self):
        df = generate_test_data()
        features = self.fe.extract_trade_features(df, 100, "long", "BOS_Pullback_Long")
        assert "direction_long" in features
        assert features["direction_long"] == 1.0
        assert "strategy_bos" in features
        assert features["strategy_bos"] == 1.0


class TestTradeClassifier:
    def setup_method(self):
        self.classifier = TradeClassifier()

    def test_default_model_creation(self):
        self.classifier._create_default_model()
        assert self.classifier.model is not None
        assert self.classifier.scaler is not None

    def test_predict_confidence(self):
        df = generate_test_data()
        self.classifier._create_default_model()
        confidence = self.classifier.predict_confidence(df)
        assert 0 <= confidence <= 1.0

    def test_predict_batch(self):
        df = generate_test_data()
        self.classifier._create_default_model()
        predictions = self.classifier.predict_batch(df)
        assert len(predictions) == len(df)
        assert all(0 <= p <= 1.0 for p in predictions)

    def test_score_setup(self):
        df = generate_test_data()
        self.classifier._create_default_model()
        score = self.classifier.score_setup(df, "long", "BOS_Pullback_Long", 0.7)
        assert 0 <= score <= 1.0

    def test_train_on_data(self):
        df = generate_test_data(n=500)
        metrics = self.classifier.train(df, n_estimators=10, max_depth=3)
        assert "accuracy" in metrics
        assert "f1_score" in metrics
        assert 0 <= metrics["accuracy"] <= 1.0

    def test_feature_importance(self):
        self.classifier._create_default_model()
        importance = self.classifier.get_feature_importance()
        assert isinstance(importance, dict)
