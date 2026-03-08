"""
Model Training Script.

Trains the RandomForest classifier on historical trade data.
Fetches completed trades from the database, engineers features,
and trains/saves the model.

Usage:
    python scripts/train_model.py
    python scripts/train_model.py --days 90 --min-samples 100
"""
import sys
import os
import asyncio
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.core.ai.classifier import TradeClassifier
from app.core.ai.features import FeatureEngineer, FEATURE_NAMES
from app.utils.logger import get_logger

logger = get_logger("train_model")


def generate_synthetic_training_data(n_samples: int = 500) -> tuple:
    """
    Generate synthetic training data for bootstrapping the model
    when no historical trade data is available.

    Features are sampled from distributions representative of good/bad setups.
    """
    logger.info(f"Generating {n_samples} synthetic training samples...")

    rng = np.random.default_rng(42)
    features_list = []
    labels = []

    for i in range(n_samples):
        # Random quality setup
        is_good = rng.random() > 0.45  # 55% positive class

        if is_good:
            # High-quality setup features
            features = {
                "close_vs_ema9": rng.normal(0.3, 0.5),
                "close_vs_ema21": rng.normal(0.5, 0.6),
                "close_vs_ema50": rng.normal(0.8, 0.7),
                "ema9_vs_ema21": rng.normal(0.2, 0.3),
                "ema21_vs_ema50": rng.normal(0.3, 0.4),
                "rsi": rng.normal(0.45, 0.1),
                "rsi_oversold": rng.choice([0.0, 1.0], p=[0.6, 0.4]),
                "rsi_overbought": 0.0,
                "macd_hist": rng.normal(0.2, 0.3),
                "macd_signal_cross": rng.choice([0.0, 1.0], p=[0.5, 0.5]),
                "atr_pct": rng.uniform(0.001, 0.005),
                "bb_width": rng.uniform(0.01, 0.04),
                "close_vs_bb_upper": rng.normal(-0.5, 0.5),
                "close_vs_bb_lower": rng.normal(0.3, 0.3),
                "body_ratio": rng.uniform(0.5, 0.9),
                "upper_wick_ratio": rng.uniform(0.01, 0.2),
                "lower_wick_ratio": rng.uniform(0.1, 0.5),
                "is_bullish_candle": rng.choice([0.0, 1.0], p=[0.4, 0.6]),
                "sweep_detected": 1.0,
                "sweep_direction": rng.choice([-1.0, 1.0]),
                "sweep_rejection_strength": rng.uniform(0.5, 1.0),
                "sweep_bars_ago": rng.uniform(1, 4),
                "bos_detected": 1.0,
                "bos_direction": rng.choice([-1.0, 1.0]),
                "bos_strength": rng.uniform(0.4, 1.0),
                "bos_bars_after_sweep": rng.uniform(1, 6),
                "h1_bias": rng.choice([-1.0, 1.0]),
                "m15_trend": rng.choice([-1.0, 1.0]),
                "mtf_aligned": 1.0,
                "alignment_score": rng.uniform(0.65, 1.0),
                "entry_zone_fvg": rng.choice([0.0, 1.0], p=[0.4, 0.6]),
                "entry_zone_ob": rng.choice([0.0, 1.0], p=[0.6, 0.4]),
                "entry_zone_50pct": rng.choice([0.0, 1.0], p=[0.7, 0.3]),
                "risk_reward": rng.uniform(0.5, 1.0),
                "is_london": rng.choice([0.0, 1.0], p=[0.3, 0.7]),
                "is_new_york": rng.choice([0.0, 1.0], p=[0.4, 0.6]),
                "is_overlap": rng.choice([0.0, 1.0], p=[0.5, 0.5]),
                "volume_ratio": rng.uniform(1.0, 3.0),
                "swing_high_dist": rng.normal(1.5, 0.5),
                "swing_low_dist": rng.normal(0.5, 0.3),
            }
            labels.append(1)
        else:
            # Low-quality setup features
            features = {
                "close_vs_ema9": rng.normal(-0.2, 0.7),
                "close_vs_ema21": rng.normal(-0.3, 0.8),
                "close_vs_ema50": rng.normal(-0.5, 1.0),
                "ema9_vs_ema21": rng.normal(-0.1, 0.5),
                "ema21_vs_ema50": rng.normal(-0.2, 0.5),
                "rsi": rng.normal(0.55, 0.15),
                "rsi_oversold": 0.0,
                "rsi_overbought": rng.choice([0.0, 1.0], p=[0.6, 0.4]),
                "macd_hist": rng.normal(-0.1, 0.4),
                "macd_signal_cross": 0.0,
                "atr_pct": rng.uniform(0.003, 0.01),
                "bb_width": rng.uniform(0.05, 0.12),
                "close_vs_bb_upper": rng.normal(0.5, 0.8),
                "close_vs_bb_lower": rng.normal(-0.3, 0.5),
                "body_ratio": rng.uniform(0.1, 0.5),
                "upper_wick_ratio": rng.uniform(0.2, 0.6),
                "lower_wick_ratio": rng.uniform(0.01, 0.2),
                "is_bullish_candle": rng.choice([0.0, 1.0], p=[0.5, 0.5]),
                "sweep_detected": rng.choice([0.0, 1.0], p=[0.5, 0.5]),
                "sweep_direction": rng.choice([-1.0, 1.0]),
                "sweep_rejection_strength": rng.uniform(0.0, 0.4),
                "sweep_bars_ago": rng.uniform(4, 10),
                "bos_detected": rng.choice([0.0, 1.0], p=[0.4, 0.6]),
                "bos_direction": rng.choice([-1.0, 1.0]),
                "bos_strength": rng.uniform(0.0, 0.3),
                "bos_bars_after_sweep": rng.uniform(8, 15),
                "h1_bias": rng.choice([-1.0, 0.0, 1.0], p=[0.4, 0.2, 0.4]),
                "m15_trend": rng.choice([-1.0, 0.0, 1.0], p=[0.4, 0.2, 0.4]),
                "mtf_aligned": rng.choice([0.0, 1.0], p=[0.6, 0.4]),
                "alignment_score": rng.uniform(0.2, 0.6),
                "entry_zone_fvg": 0.0,
                "entry_zone_ob": 0.0,
                "entry_zone_50pct": rng.choice([0.0, 1.0], p=[0.5, 0.5]),
                "risk_reward": rng.uniform(0.0, 0.4),
                "is_london": rng.choice([0.0, 1.0], p=[0.5, 0.5]),
                "is_new_york": rng.choice([0.0, 1.0], p=[0.5, 0.5]),
                "is_overlap": 0.0,
                "volume_ratio": rng.uniform(0.5, 1.5),
                "swing_high_dist": rng.normal(0.5, 1.0),
                "swing_low_dist": rng.normal(0.3, 0.8),
            }
            labels.append(0)

        features_list.append(features)

    return features_list, labels


async def train_from_database(days: int = 90):
    """Load historical trades from DB and train model."""
    from app.database import AsyncSessionLocal
    from app.models.trade import Trade, TradeStatus
    from sqlalchemy import select
    from datetime import datetime, timedelta, timezone

    since = datetime.now(timezone.utc) - timedelta(days=days)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Trade)
            .where(Trade.status == TradeStatus.CLOSED)
            .where(Trade.closed_at >= since)
        )
        trades = result.scalars().all()

    logger.info(f"Found {len(trades)} closed trades in last {days} days")
    return trades


def main():
    parser = argparse.ArgumentParser(description="Train AI Trade Classifier")
    parser.add_argument("--days", type=int, default=90, help="Days of history to use")
    parser.add_argument("--min-samples", type=int, default=100, help="Minimum samples required")
    parser.add_argument("--synthetic", action="store_true", default=False,
                        help="Force use synthetic data (for initial bootstrap)")
    parser.add_argument("--n-synthetic", type=int, default=1000,
                        help="Number of synthetic samples")
    parser.add_argument("--model-path", type=str, default=None, help="Output model path")
    args = parser.parse_args()

    model_path = args.model_path or settings.MODEL_PATH
    os.makedirs(os.path.dirname(model_path), exist_ok=True)

    classifier = TradeClassifier(model_path=model_path)
    feature_engineer = FeatureEngineer()

    use_synthetic = args.synthetic

    if not use_synthetic:
        # Try to load from DB
        try:
            trades = asyncio.run(train_from_database(args.days))
            if len(trades) < args.min_samples:
                logger.warning(
                    f"Only {len(trades)} trades found (min: {args.min_samples}). "
                    f"Using synthetic data for bootstrapping."
                )
                use_synthetic = True
        except Exception as e:
            logger.error(f"Database load failed: {e}")
            use_synthetic = True

    if use_synthetic:
        logger.info(f"Training with {args.n_synthetic} synthetic samples...")
        features_list, labels = generate_synthetic_training_data(args.n_synthetic)
    else:
        # Build features from real trades
        features_list = []
        labels = []
        for trade in trades:
            features = {name: 0.0 for name in FEATURE_NAMES}
            if trade.ai_confidence:
                features["alignment_score"] = trade.ai_confidence
            if trade.session:
                features["is_london"] = 1.0 if "london" in trade.session else 0.0
                features["is_new_york"] = 1.0 if "new_york" in trade.session else 0.0
                features["is_overlap"] = 1.0 if "overlap" in trade.session else 0.0
            label = 1 if (trade.pnl or 0) > 0 else 0
            features_list.append(features)
            labels.append(label)

    # Train
    logger.info("Starting model training...")
    metrics = classifier.train(features_list, labels, save=True)

    print("\n" + "=" * 50)
    print("TRAINING COMPLETE")
    print("=" * 50)
    for k, v in metrics.items():
        print(f"  {k}: {v}")
    print(f"\nModel saved to: {model_path}")
    print("=" * 50)

    # Print feature importance
    importance = classifier.get_feature_importance()
    print("\nTop 10 Feature Importances:")
    for i, (feat, imp) in enumerate(list(importance.items())[:10]):
        print(f"  {i+1:2d}. {feat:<30s} {imp:.4f}")


if __name__ == "__main__":
    main()
