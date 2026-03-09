"""
Dataset Builder.

Collects and prepares labeled training data for the AI classifier.

Two data sources:
1. Historical closed trades from PostgreSQL (with known outcomes)
2. Synthetic data generator (for bootstrapping when no real data exists)

Labelling logic:
  label = 1 if trade.pnl > 0 else 0

Feature extraction is delegated to app.core.ai.features.FeatureEngineer.
"""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple, Optional
import numpy as np

from app.core.ai.features import FeatureEngineer, FEATURE_NAMES
from app.utils.logger import get_logger

logger = get_logger("dataset_builder")

UTC = timezone.utc


class DatasetBuilder:
    """
    Builds a training dataset from historical trades + optional synthetic data.
    """

    def __init__(self):
        self.feature_engineer = FeatureEngineer()

    async def from_database(
        self,
        days: int = 180,
        min_samples: int = 50,
    ) -> Tuple[List[Dict], List[int]]:
        """
        Load closed trades from DB and build feature/label pairs.

        Returns (features_list, labels) where features_list[i] is a dict
        and labels[i] is 0 or 1.
        """
        try:
            from app.database import AsyncSessionLocal
            from app.models.trade import Trade, TradeStatus
            from sqlalchemy import select

            since = datetime.now(UTC) - timedelta(days=days)

            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Trade)
                    .where(Trade.status == TradeStatus.CLOSED)
                    .where(Trade.closed_at >= since)
                )
                trades = result.scalars().all()

        except Exception as e:
            logger.warning(f"DB load failed: {e}")
            return [], []

        if len(trades) < min_samples:
            logger.warning(
                f"Only {len(trades)} closed trades (min={min_samples}). "
                "Consider adding synthetic data."
            )

        features_list = []
        labels = []

        for trade in trades:
            features = self._features_from_trade(trade)
            label = 1 if (trade.pnl or 0) > 0 else 0
            features_list.append(features)
            labels.append(label)

        logger.info(
            f"Dataset from DB: {len(features_list)} samples, "
            f"{sum(labels)} positive ({100*sum(labels)/max(len(labels),1):.1f}%)"
        )
        return features_list, labels

    def from_backtest(
        self,
        trade_log: List[dict],
        signal_features: Optional[List[dict]] = None,
    ) -> Tuple[List[Dict], List[int]]:
        """
        Build dataset from backtest trade_log.

        trade_log items must have: pnl, direction, exit_reason, slippage_pips, spread_pips.
        signal_features (optional) are the AI feature dicts produced during backtest scanning.
        """
        features_list = []
        labels = []

        for i, trade in enumerate(trade_log):
            if signal_features and i < len(signal_features):
                features = signal_features[i]
            else:
                features = self._features_from_backtest_trade(trade)
            label = 1 if trade.get("pnl", 0) > 0 else 0
            features_list.append(features)
            labels.append(label)

        logger.info(
            f"Dataset from backtest: {len(features_list)} samples, "
            f"{sum(labels)} wins ({100*sum(labels)/max(len(labels),1):.1f}%)"
        )
        return features_list, labels

    def generate_synthetic(
        self,
        n_samples: int = 1000,
        positive_rate: float = 0.52,
        seed: int = 42,
    ) -> Tuple[List[Dict], List[int]]:
        """
        Generate synthetic training data with realistic feature distributions.

        The distributions are calibrated so that:
        - High-quality setups (positive class) show strong alignment,
          low sweep_bars_ago, high bos_strength, FVG entry
        - Low-quality setups (negative class) show weak/conflicting signals
        """
        rng = np.random.default_rng(seed)
        features_list = []
        labels = []

        for i in range(n_samples):
            is_positive = rng.random() < positive_rate
            features = self._synthetic_sample(rng, is_positive)
            features_list.append(features)
            labels.append(1 if is_positive else 0)

        logger.info(f"Generated {n_samples} synthetic samples ({positive_rate:.0%} positive)")
        return features_list, labels

    def merge(
        self,
        *datasets: Tuple[List[Dict], List[int]],
        shuffle: bool = True,
        seed: int = 42,
    ) -> Tuple[List[Dict], List[int]]:
        """Merge multiple (features, labels) datasets."""
        merged_f: List[Dict] = []
        merged_l: List[int] = []
        for f, l in datasets:
            merged_f.extend(f)
            merged_l.extend(l)

        if shuffle:
            rng = np.random.default_rng(seed)
            indices = rng.permutation(len(merged_f))
            merged_f = [merged_f[i] for i in indices]
            merged_l = [merged_l[i] for i in indices]

        logger.info(
            f"Merged dataset: {len(merged_f)} samples, "
            f"{sum(merged_l)} positive ({100*sum(merged_l)/max(len(merged_l),1):.1f}%)"
        )
        return merged_f, merged_l

    def to_arrays(
        self,
        features_list: List[Dict],
        labels: List[int],
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Convert to numpy arrays for sklearn."""
        X = np.array([
            [features.get(name, 0.0) for name in FEATURE_NAMES]
            for features in features_list
        ])
        y = np.array(labels)
        X = np.nan_to_num(X, nan=0.0, posinf=2.0, neginf=-2.0)
        return X, y

    # ── Private ────────────────────────────────────────────────────────

    def _features_from_trade(self, trade) -> Dict:
        """Build feature dict from a Trade ORM object (limited info available)."""
        features = {name: 0.0 for name in FEATURE_NAMES}

        if trade.ai_confidence:
            features["alignment_score"] = trade.ai_confidence

        session = trade.session or ""
        features["is_london"] = 1.0 if "london" in session.lower() else 0.0
        features["is_new_york"] = 1.0 if "new_york" in session.lower() else 0.0
        features["is_overlap"] = 1.0 if "overlap" in session.lower() else 0.0

        direction_map = {"long": 1.0, "short": -1.0}
        if trade.direction:
            features["bos_direction"] = direction_map.get(str(trade.direction).lower(), 0.0)

        if trade.risk_reward_ratio and trade.risk_reward_ratio > 0:
            features["risk_reward"] = min(trade.risk_reward_ratio / 5.0, 1.0)

        # Derive sweep/BOS from signal if stored in ai_features
        if hasattr(trade, "meta_data") and trade.meta_data:
            for k, v in (trade.meta_data or {}).items():
                if k in FEATURE_NAMES:
                    features[k] = float(v)

        return features

    def _features_from_backtest_trade(self, trade: dict) -> Dict:
        features = {name: 0.0 for name in FEATURE_NAMES}
        features["bos_direction"] = 1.0 if trade.get("direction") == "long" else -1.0
        features["risk_reward"] = min(abs(trade.get("mfe", 0)) / max(abs(trade.get("mae", 1)), 1) / 5.0, 1.0)
        return features

    def _synthetic_sample(self, rng: np.random.Generator, is_positive: bool) -> Dict:
        if is_positive:
            return {
                "close_vs_ema9": rng.normal(0.4, 0.5),
                "close_vs_ema21": rng.normal(0.6, 0.6),
                "close_vs_ema50": rng.normal(0.9, 0.7),
                "ema9_vs_ema21": rng.normal(0.2, 0.3),
                "ema21_vs_ema50": rng.normal(0.3, 0.4),
                "rsi": rng.uniform(0.35, 0.55),
                "rsi_oversold": float(rng.random() > 0.6),
                "rsi_overbought": 0.0,
                "macd_hist": rng.normal(0.3, 0.3),
                "macd_signal_cross": float(rng.random() > 0.5),
                "atr_pct": rng.uniform(0.001, 0.004),
                "bb_width": rng.uniform(0.01, 0.04),
                "close_vs_bb_upper": rng.normal(-0.5, 0.5),
                "close_vs_bb_lower": rng.normal(0.4, 0.3),
                "body_ratio": rng.uniform(0.55, 0.95),
                "upper_wick_ratio": rng.uniform(0.01, 0.2),
                "lower_wick_ratio": rng.uniform(0.1, 0.45),
                "is_bullish_candle": float(rng.random() > 0.4),
                "sweep_detected": 1.0,
                "sweep_direction": float(rng.choice([-1.0, 1.0])),
                "sweep_rejection_strength": rng.uniform(0.55, 1.0),
                "sweep_bars_ago": rng.uniform(1, 4),
                "bos_detected": 1.0,
                "bos_direction": float(rng.choice([-1.0, 1.0])),
                "bos_strength": rng.uniform(0.45, 1.0),
                "bos_bars_after_sweep": rng.uniform(1, 6),
                "h1_bias": float(rng.choice([-1.0, 1.0])),
                "m15_trend": float(rng.choice([-1.0, 1.0])),
                "mtf_aligned": 1.0,
                "alignment_score": rng.uniform(0.70, 1.0),
                "entry_zone_fvg": float(rng.random() > 0.45),
                "entry_zone_ob": float(rng.random() > 0.65),
                "entry_zone_50pct": float(rng.random() > 0.75),
                "risk_reward": rng.uniform(0.45, 1.0),
                "is_london": float(rng.random() > 0.35),
                "is_new_york": float(rng.random() > 0.45),
                "is_overlap": float(rng.random() > 0.55),
                "volume_ratio": rng.uniform(1.2, 3.5),
                "swing_high_dist": rng.normal(1.5, 0.6),
                "swing_low_dist": rng.normal(0.4, 0.3),
            }
        else:
            return {
                "close_vs_ema9": rng.normal(-0.3, 0.8),
                "close_vs_ema21": rng.normal(-0.4, 0.9),
                "close_vs_ema50": rng.normal(-0.6, 1.1),
                "ema9_vs_ema21": rng.normal(-0.2, 0.5),
                "ema21_vs_ema50": rng.normal(-0.2, 0.6),
                "rsi": rng.uniform(0.4, 0.65),
                "rsi_oversold": 0.0,
                "rsi_overbought": float(rng.random() > 0.55),
                "macd_hist": rng.normal(-0.2, 0.5),
                "macd_signal_cross": 0.0,
                "atr_pct": rng.uniform(0.004, 0.012),
                "bb_width": rng.uniform(0.05, 0.14),
                "close_vs_bb_upper": rng.normal(0.4, 0.9),
                "close_vs_bb_lower": rng.normal(-0.3, 0.5),
                "body_ratio": rng.uniform(0.1, 0.5),
                "upper_wick_ratio": rng.uniform(0.2, 0.65),
                "lower_wick_ratio": rng.uniform(0.01, 0.25),
                "is_bullish_candle": float(rng.random() > 0.5),
                "sweep_detected": float(rng.random() > 0.5),
                "sweep_direction": float(rng.choice([-1.0, 1.0])),
                "sweep_rejection_strength": rng.uniform(0.0, 0.45),
                "sweep_bars_ago": rng.uniform(4, 10),
                "bos_detected": float(rng.random() > 0.45),
                "bos_direction": float(rng.choice([-1.0, 1.0])),
                "bos_strength": rng.uniform(0.0, 0.35),
                "bos_bars_after_sweep": rng.uniform(8, 15),
                "h1_bias": float(rng.choice([-1.0, 0.0, 1.0])),
                "m15_trend": float(rng.choice([-1.0, 0.0, 1.0])),
                "mtf_aligned": float(rng.random() > 0.6),
                "alignment_score": rng.uniform(0.2, 0.58),
                "entry_zone_fvg": 0.0,
                "entry_zone_ob": 0.0,
                "entry_zone_50pct": float(rng.random() > 0.5),
                "risk_reward": rng.uniform(0.0, 0.35),
                "is_london": float(rng.random() > 0.5),
                "is_new_york": float(rng.random() > 0.5),
                "is_overlap": 0.0,
                "volume_ratio": rng.uniform(0.5, 1.5),
                "swing_high_dist": rng.normal(0.5, 1.2),
                "swing_low_dist": rng.normal(0.3, 0.9),
            }
