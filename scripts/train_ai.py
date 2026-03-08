"""
Standalone script to retrain the AI classifier from historical trade data.

Usage:
    python scripts/train_ai.py
    python scripts/train_ai.py --min-samples 50
"""

import asyncio
import sys
import argparse
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from config.logging_config import setup_logging
from src.ai.classifier import TradeClassifier
from src.models.database import Trade, TradeStatus, AsyncSessionLocal, init_db
from sqlalchemy import select


async def main(min_samples: int = 30):
    setup_logging()
    logger.info("Starting AI model training")

    await init_db()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Trade)
            .where(Trade.status == TradeStatus.CLOSED)
            .order_by(Trade.close_time.desc())
            .limit(2000)
        )
        trades = result.scalars().all()

    logger.info(f"Found {len(trades)} closed trades")

    trade_dicts = [
        {
            "ai_features": t.metadata_.get("ai_features", {}),
            "realized_pnl": float(t.realized_pnl),
        }
        for t in trades
    ]

    classifier = TradeClassifier()
    X, y = classifier.build_training_data_from_trades(trade_dicts)

    if len(X) < min_samples:
        logger.error(f"Insufficient training samples: {len(X)} < {min_samples}")
        logger.info("Run the bot in paper mode for a while to accumulate trade data")
        return

    result = classifier.train(X, y)
    logger.info(f"Training complete: {result}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-samples", type=int, default=30)
    args = parser.parse_args()
    asyncio.run(main(args.min_samples))
