"""RandomForest classifier for trade confidence scoring."""
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    RandomForestClassifier = None
    StandardScaler = None


MODEL_PATH = Path(__file__).parent / "models" / "rf_classifier.joblib"
SCALER_PATH = Path(__file__).parent / "models" / "scaler.joblib"


def build_feature_vector(
    ohlcv_h1: pd.DataFrame,
    ohlcv_m15: pd.DataFrame,
    ohlcv_m5: pd.DataFrame,
    signal_direction: str,
    strategy_type: str,
) -> np.ndarray:
    """
    Build feature vector for ML model.
    Features: price action, structure, volatility, momentum.
    """
    if len(ohlcv_m5) < 50 or len(ohlcv_m15) < 50 or len(ohlcv_h1) < 50:
        return np.zeros(20)  # Fallback

    # Returns
    m5_ret = ohlcv_m5["close"].pct_change().dropna()
    m15_ret = ohlcv_m15["close"].pct_change().dropna()
    h1_ret = ohlcv_h1["close"].pct_change().dropna()

    # Volatility (ATR-based)
    def atr_vol(df):
        h, l, c = df["high"], df["low"], df["close"]
        tr = np.maximum(h - l, np.maximum((h - c.shift(1)).abs(), (l - c.shift(1)).abs()))
        return tr.rolling(14).mean().iloc[-1] / df["close"].iloc[-1] if len(df) >= 14 else 0

    vol_m5 = atr_vol(ohlcv_m5)
    vol_m15 = atr_vol(ohlcv_m15)
    vol_h1 = atr_vol(ohlcv_h1)

    # Momentum
    mom_m5 = (ohlcv_m5["close"].iloc[-1] / ohlcv_m5["close"].iloc[-10] - 1) if len(ohlcv_m5) >= 10 else 0
    mom_m15 = (ohlcv_m15["close"].iloc[-1] / ohlcv_m15["close"].iloc[-10] - 1) if len(ohlcv_m15) >= 10 else 0
    mom_h1 = (ohlcv_h1["close"].iloc[-1] / ohlcv_h1["close"].iloc[-10] - 1) if len(ohlcv_h1) >= 10 else 0

    # Structure alignment (simplified)
    h1_trend = 1 if ohlcv_h1["close"].iloc[-1] > ohlcv_h1["close"].iloc[-20] else -1
    m15_trend = 1 if ohlcv_m15["close"].iloc[-1] > ohlcv_m15["close"].iloc[-20] else -1
    direction_mult = 1 if signal_direction == "long" else -1
    alignment = 1 if h1_trend == direction_mult and m15_trend == direction_mult else 0

    # Strategy encoding
    strat_map = {"liquidity_sweep": 0, "break_of_structure": 1, "pullback_entry": 2}
    strat_enc = strat_map.get(strategy_type, 0)

    features = [
        m5_ret.tail(5).mean(), m5_ret.tail(5).std() or 0,
        m15_ret.tail(5).mean(), m15_ret.tail(5).std() or 0,
        h1_ret.tail(5).mean(), h1_ret.tail(5).std() or 0,
        vol_m5, vol_m15, vol_h1,
        mom_m5, mom_m15, mom_h1,
        h1_trend, m15_trend, alignment,
        strat_enc, direction_mult,
        ohlcv_m5["close"].iloc[-1] / ohlcv_m5["close"].iloc[-20] - 1,
        ohlcv_m15["close"].iloc[-1] / ohlcv_m15["close"].iloc[-20] - 1,
    ]
    return np.array(features, dtype=np.float64).reshape(1, -1)


class TradeClassifier:
    """RandomForest-based trade confidence scorer."""

    def __init__(self, n_estimators: int = 100, min_confidence: float = 0.6):
        self.min_confidence = min_confidence
        self.model = RandomForestClassifier(n_estimators=n_estimators, random_state=42) if SKLEARN_AVAILABLE else None
        self.scaler = StandardScaler() if SKLEARN_AVAILABLE else None
        self.scaler_fitted = False

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        """Train the classifier. y: 1 = profitable, 0 = loss."""
        if not SKLEARN_AVAILABLE or self.model is None:
            return
        X_scaled = self.scaler.fit_transform(X)
        self.scaler_fitted = True
        self.model.fit(X_scaled, y)

    def predict_confidence(self, X: np.ndarray) -> float:
        """
        Predict probability of profitable trade (confidence).
        Returns value in [0, 1].
        """
        if not SKLEARN_AVAILABLE or self.model is None:
            return 0.65  # Default confidence when no model

        if not self.scaler_fitted:
            return 0.65

        try:
            X_scaled = self.scaler.transform(X)
            proba = self.model.predict_proba(X_scaled)
            if proba.shape[1] >= 2:
                return float(proba[0, 1])
            return float(proba[0, 0])
        except Exception:
            return 0.65

    def score_signal(
        self,
        ohlcv_h1: pd.DataFrame,
        ohlcv_m15: pd.DataFrame,
        ohlcv_m5: pd.DataFrame,
        signal_direction: str,
        strategy_type: str,
    ) -> float:
        """Score a trade signal with confidence."""
        X = build_feature_vector(ohlcv_h1, ohlcv_m15, ohlcv_m5, signal_direction, strategy_type)
        return self.predict_confidence(X)

    def save(self, path: Optional[Path] = None, scaler_path: Optional[Path] = None) -> None:
        """Save model and scaler."""
        if not SKLEARN_AVAILABLE:
            return
        try:
            import joblib
            path = path or MODEL_PATH
            scaler_path = scaler_path or SCALER_PATH
            path.parent.mkdir(parents=True, exist_ok=True)
            joblib.dump(self.model, path)
            joblib.dump(self.scaler, scaler_path)
        except Exception:
            pass

    def load(self, path: Optional[Path] = None, scaler_path: Optional[Path] = None) -> bool:
        """Load model and scaler."""
        if not SKLEARN_AVAILABLE:
            return False
        try:
            import joblib
            path = path or MODEL_PATH
            scaler_path = scaler_path or SCALER_PATH
            if not path.exists():
                return False
            self.model = joblib.load(path)
            self.scaler = joblib.load(scaler_path)
            self.scaler_fitted = True
            return True
        except Exception:
            return False
