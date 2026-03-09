"""
Anomaly detection for live strategy monitoring.

Detects performance degradation, regime changes, and unusual
behavior patterns that may indicate strategy breakdown.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class AnomalyType(Enum):
    RETURN_OUTLIER = "return_outlier"
    VOLATILITY_SPIKE = "volatility_spike"
    SHARPE_DEGRADATION = "sharpe_degradation"
    DRAWDOWN_ALERT = "drawdown_alert"
    CORRELATION_BREAK = "correlation_break"
    TURNOVER_SPIKE = "turnover_spike"
    VOLUME_ANOMALY = "volume_anomaly"


@dataclass
class Anomaly:
    anomaly_type: AnomalyType
    severity: float  # 0 to 1
    timestamp: float = 0.0
    strategy_id: str = ""
    details: str = ""
    value: float = 0.0
    threshold: float = 0.0


class AnomalyDetector:
    """
    Real-time anomaly detection for strategy monitoring.

    Uses rolling statistics and z-score thresholds to detect
    unusual behavior in strategy returns and risk metrics.
    """

    def __init__(self, zscore_threshold: float = 3.0) -> None:
        self.threshold = zscore_threshold
        self._history: dict[str, list[float]] = {}
        self._alerts: list[Anomaly] = []

    def check_return(
        self,
        strategy_id: str,
        daily_return: float,
        lookback: int = 63,
    ) -> list[Anomaly]:
        """Check for abnormal returns."""
        key = f"{strategy_id}_returns"
        self._history.setdefault(key, []).append(daily_return)
        history = self._history[key]

        anomalies = []
        if len(history) < lookback:
            return anomalies

        recent = np.array(history[-lookback:])
        mean = recent[:-1].mean()
        std = recent[:-1].std()

        if std > 0:
            z = abs(daily_return - mean) / std
            if z > self.threshold:
                severity = min(1.0, z / (2 * self.threshold))
                anomaly = Anomaly(
                    anomaly_type=AnomalyType.RETURN_OUTLIER,
                    severity=severity,
                    strategy_id=strategy_id,
                    details=f"Return z-score: {z:.2f} (threshold: {self.threshold})",
                    value=z,
                    threshold=self.threshold,
                )
                anomalies.append(anomaly)
                logger.warning("Anomaly: %s return z-score %.2f", strategy_id, z)

        return anomalies

    def check_volatility(
        self,
        strategy_id: str,
        current_vol: float,
        baseline_vol: float,
        multiplier: float = 2.0,
    ) -> list[Anomaly]:
        """Check for volatility spikes."""
        anomalies = []
        if baseline_vol > 0 and current_vol > baseline_vol * multiplier:
            severity = min(1.0, (current_vol / baseline_vol - 1) / 3)
            anomalies.append(Anomaly(
                anomaly_type=AnomalyType.VOLATILITY_SPIKE,
                severity=severity,
                strategy_id=strategy_id,
                details=f"Vol spike: {current_vol:.4f} vs baseline {baseline_vol:.4f}",
                value=current_vol,
                threshold=baseline_vol * multiplier,
            ))
        return anomalies

    def check_sharpe_degradation(
        self,
        strategy_id: str,
        rolling_sharpe: float,
        historical_sharpe: float,
        degradation_threshold: float = 0.5,
    ) -> list[Anomaly]:
        """Check for significant Sharpe ratio degradation."""
        anomalies = []
        if historical_sharpe > 0:
            ratio = rolling_sharpe / historical_sharpe
            if ratio < degradation_threshold:
                severity = min(1.0, 1 - ratio)
                anomalies.append(Anomaly(
                    anomaly_type=AnomalyType.SHARPE_DEGRADATION,
                    severity=severity,
                    strategy_id=strategy_id,
                    details=f"Sharpe degraded to {rolling_sharpe:.2f} from {historical_sharpe:.2f}",
                    value=rolling_sharpe,
                    threshold=historical_sharpe * degradation_threshold,
                ))
        return anomalies

    def check_drawdown(
        self,
        strategy_id: str,
        current_drawdown: float,
        threshold: float = 0.05,
    ) -> list[Anomaly]:
        """Alert on significant drawdowns."""
        anomalies = []
        if current_drawdown > threshold:
            severity = min(1.0, current_drawdown / (2 * threshold))
            anomalies.append(Anomaly(
                anomaly_type=AnomalyType.DRAWDOWN_ALERT,
                severity=severity,
                strategy_id=strategy_id,
                details=f"Drawdown: {current_drawdown:.2%} (threshold: {threshold:.2%})",
                value=current_drawdown,
                threshold=threshold,
            ))
        return anomalies

    def get_all_anomalies(self) -> list[Anomaly]:
        return list(self._alerts)

    def clear_history(self) -> None:
        self._history.clear()
        self._alerts.clear()
