from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler


class TradeConfidenceModel:
    def __init__(self) -> None:
        self.model = RandomForestClassifier(
            n_estimators=200, max_depth=8, min_samples_split=6, random_state=42
        )
        self.scaler = StandardScaler()
        self.is_trained = False

    @staticmethod
    def _features(df: pd.DataFrame) -> pd.DataFrame:
        feat = pd.DataFrame(index=df.index)
        feat["ret_1"] = df["close"].pct_change(1).fillna(0)
        feat["ret_3"] = df["close"].pct_change(3).fillna(0)
        feat["ret_5"] = df["close"].pct_change(5).fillna(0)
        feat["range"] = ((df["high"] - df["low"]) / df["close"]).fillna(0)
        feat["body"] = ((df["close"] - df["open"]).abs() / df["close"]).fillna(0)
        feat["vol_chg"] = df["volume"].pct_change(3).replace([np.inf, -np.inf], 0).fillna(0)
        return feat

    def train(self, df: pd.DataFrame) -> None:
        feat = self._features(df)
        target = (df["close"].shift(-3) > df["close"]).astype(int).fillna(0)
        X = feat.iloc[:-3].values
        y = target.iloc[:-3].values
        if len(X) < 50:
            return
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y)
        self.is_trained = True

    def confidence(self, df: pd.DataFrame) -> float:
        if not self.is_trained:
            self.train(df)
        if not self.is_trained:
            return 0.5
        feat = self._features(df).iloc[[-1]].values
        X_scaled = self.scaler.transform(feat)
        probabilities = self.model.predict_proba(X_scaled)[0]
        return float(max(probabilities))
