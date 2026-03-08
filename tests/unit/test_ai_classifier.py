"""Tests for the AI classifier and feature engineering."""
import pytest
import numpy as np
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.ai.feature_engineering import extract_features, FEATURE_NAMES, N_FEATURES
from src.ai.classifier import TradeClassifier


def make_mock_signal(direction="bullish", confidence=0.6, rr=2.0):
    """Create a mock MTFSignal for testing."""
    from src.strategy.break_of_structure import BOSResult
    from src.strategy.liquidity_sweep import SweepResult
    from src.strategy.pullback_entry import PullbackResult
    from src.strategy.multi_timeframe import MTFSignal, TimeframeAnalysis
    import pandas as pd

    bos = BOSResult(detected=True, bos_type="bullish_bos", broken_level=1.1050,
                    break_bar=10, trend="bullish", strength=0.7)
    sweep = SweepResult(detected=True, direction="bullish", swept_level=1.0950,
                        sweep_low=1.0940, sweep_high=1.0960, reversal_bar=5, strength=0.8)
    pullback = PullbackResult(valid=True, entry_type="order_block",
                               entry_zone_high=1.1010, entry_zone_low=1.0990,
                               suggested_entry=1.1000, fib_retracement=0.65,
                               ob_high=1.1010, ob_low=1.0990, fvg=None)

    tf = TimeframeAnalysis(
        timeframe="M5", trend=direction, bos=bos, sweep=sweep, pullback=pullback,
        atr=0.0005, ema_fast=1.1005, ema_slow=1.0995, rsi=52.0,
        current_price=1.1000, raw_df=pd.DataFrame({
            "open": [1.0995], "high": [1.1010], "low": [1.0985], "close": [1.1000], "volume": [500.0]
        }),
    )

    return MTFSignal(
        symbol="EURUSD", market="forex", direction=direction,
        valid=True, confidence=confidence,
        htf=tf, mtf=tf, ltf=tf,
        entry_price=1.1000, stop_loss=1.0950, tp1=1.1050, tp2=1.1075, tp3=1.1100,
        atr=0.0005, risk_reward=rr,
    )


def test_feature_vector_shape():
    signal = make_mock_signal()
    features = extract_features(signal)
    assert features.shape == (N_FEATURES,)


def test_feature_names_count():
    assert len(FEATURE_NAMES) == N_FEATURES


def test_no_nan_in_features():
    signal = make_mock_signal()
    features = extract_features(signal)
    assert not np.isnan(features).any()
    assert not np.isinf(features).any()


def test_features_range():
    signal = make_mock_signal()
    features = extract_features(signal)
    # RSI normalized should be in [0, 1]
    rsi_idx = FEATURE_NAMES.index("htf_rsi")
    assert 0.0 <= features[rsi_idx] <= 1.0


def test_classifier_rule_based_scoring():
    classifier = TradeClassifier()
    signal = make_mock_signal(confidence=0.7)
    score = classifier.predict_confidence(signal)
    assert 0.0 <= score <= 1.0


def test_classifier_trained_flag_initially_false_or_loaded():
    classifier = TradeClassifier()
    # Either trained (if model file exists) or not
    assert isinstance(classifier._trained, bool)


def test_classifier_build_training_data_empty():
    classifier = TradeClassifier()
    X, y = classifier.build_training_data_from_trades([])
    assert X.shape[0] == 0
    assert y.shape[0] == 0


def test_classifier_build_training_data_valid():
    classifier = TradeClassifier()
    signal = make_mock_signal()
    features = extract_features(signal)
    feature_dict = {name: float(val) for name, val in zip(FEATURE_NAMES, features)}

    trades = [
        {"ai_features": feature_dict, "realized_pnl": 50.0},
        {"ai_features": feature_dict, "realized_pnl": -20.0},
        {"ai_features": feature_dict, "realized_pnl": 30.0},
    ]
    X, y = classifier.build_training_data_from_trades(trades)
    assert X.shape == (3, N_FEATURES)
    assert len(y) == 3
    assert set(y).issubset({0, 1})


def test_classifier_train_with_sufficient_data():
    classifier = TradeClassifier()
    signal = make_mock_signal()
    features = extract_features(signal)
    feature_dict = {name: float(val) for name, val in zip(FEATURE_NAMES, features)}

    trades = [
        {"ai_features": feature_dict, "realized_pnl": 50.0 if i % 2 == 0 else -20.0}
        for i in range(40)
    ]
    X, y = classifier.build_training_data_from_trades(trades)
    result = classifier.train(X, y)
    assert result.get("trained") is True
    assert "cv_auc" in result


def test_classifier_confidence_bullish_vs_bearish():
    classifier = TradeClassifier()
    bull = make_mock_signal("bullish", confidence=0.75, rr=2.0)
    bear = make_mock_signal("bearish", confidence=0.45, rr=1.0)
    score_bull = classifier.predict_confidence(bull)
    score_bear = classifier.predict_confidence(bear)
    # Higher structural confidence should give higher score
    assert score_bull >= score_bear
