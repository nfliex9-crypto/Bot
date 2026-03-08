import pytest
import numpy as np

from app.ai.classifier import TradeClassifier
from app.ai.feature_engineer import FEATURE_NAMES, generate_synthetic_training_data, setup_to_features
from app.strategy.engine import TradeSetup


@pytest.fixture
def classifier():
    clf = TradeClassifier()
    clf.train_initial()
    return clf


def test_train_creates_model(classifier):
    assert classifier._model is not None


def test_predict_returns_float(classifier):
    setup = TradeSetup(
        symbol="EURUSD",
        direction="long",
        entry_price=1.1000,
        stop_loss=1.0950,
        tp1=1.1050,
        tp2=1.1075,
        tp3=1.1100,
        atr_value=0.0010,
        confidence_features={
            "direction": 1.0,
            "h1_bias_aligned": 1.0,
            "m15_bos_count": 3.0,
            "m5_bos_count": 2.0,
            "pullback_distance_atr": 0.5,
            "atr_value": 0.001,
            "rsi_m5": 45.0,
            "ema_distance": 0.3,
            "sweep_wick_size": 0.002,
        },
    )
    conf = classifier.predict_confidence(setup)
    assert 0.0 <= conf <= 1.0


def test_feature_importance(classifier):
    importance = classifier.get_feature_importance()
    assert len(importance) == len(FEATURE_NAMES)
    assert all(v >= 0 for v in importance.values())


def test_synthetic_data_shape():
    X, y = generate_synthetic_training_data(100)
    assert X.shape == (100, len(FEATURE_NAMES))
    assert y.shape == (100,)
    assert set(np.unique(y)).issubset({0, 1})
