"""Tests for the AI layer."""
from __future__ import annotations

import numpy as np
import pytest

from ai.features import FEATURE_COLUMNS, signal_features_to_array, trades_to_training_data
from ai.model import TradingAIModel
from ai.scorer import ConfidenceScorer
from core.enums import Direction, Market, SignalType
from core.models import TradeSignal


def _make_features() -> dict:
    return {
        "atr_m5": 0.0012,
        "atr_m15": 0.0018,
        "atr_h1": 0.0035,
        "rsi": 45.0,
        "volume_ratio": 1.2,
        "body_ratio": 0.6,
        "ema_spread": 0.0005,
        "bias_bullish": 1.0,
        "bias_bearish": 0.0,
        "signal_liquidity": 0.0,
        "signal_bos": 0.0,
        "signal_pullback": 1.0,
        "risk_reward": 1.8,
        "num_liquidity_zones": 3.0,
    }


class TestFeatures:

    def test_feature_array_shape(self):
        arr = signal_features_to_array(_make_features())
        assert arr.shape == (1, len(FEATURE_COLUMNS))

    def test_training_data_insufficient(self):
        X, y = trades_to_training_data([])
        assert X is None and y is None

    def test_training_data_with_samples(self):
        trades = []
        for i in range(25):
            trades.append({
                "pnl": 10.0 if i % 2 == 0 else -5.0,
                "metadata_json": {"features": _make_features()},
            })
        X, y = trades_to_training_data(trades)
        assert X is not None
        assert X.shape == (25, len(FEATURE_COLUMNS))
        assert len(y) == 25


class TestAIModel:

    def test_untrained_returns_default(self):
        model = TradingAIModel()
        model._is_trained = False
        model._model = None
        conf = model.predict_confidence(_make_features())
        assert conf == 0.75

    def test_train_and_predict(self):
        model = TradingAIModel()
        trades = []
        rng = np.random.RandomState(42)
        for i in range(50):
            feat = _make_features()
            feat["rsi"] = float(rng.uniform(20, 80))
            feat["volume_ratio"] = float(rng.uniform(0.5, 2.5))
            trades.append({
                "pnl": float(rng.choice([10.0, -5.0])),
                "metadata_json": {"features": feat},
            })
        metrics = model.train(trades)
        assert metrics is not None
        assert "f1_score" in metrics
        assert model.is_trained

        conf = model.predict_confidence(_make_features())
        assert 0.0 <= conf <= 1.0


class TestScorer:

    def test_confidence_scoring(self):
        model = TradingAIModel()
        scorer = ConfidenceScorer(model)
        signal = TradeSignal(
            symbol="EURUSD",
            market=Market.FOREX,
            direction=Direction.LONG,
            signal_type=SignalType.PULLBACK_ENTRY,
            entry_price=1.1000,
            stop_loss=1.0960,
            tp1=1.1040,
            tp2=1.1060,
            tp3=1.1080,
            risk_reward=2.0,
            features=_make_features(),
        )
        conf = scorer.score(signal)
        assert 0.0 <= conf <= 1.0
