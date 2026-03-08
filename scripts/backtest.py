"""
Simple backtesting script using historical data.

Runs the full strategy pipeline on historical OHLCV data to evaluate
signal quality and expected performance.

Usage:
    python scripts/backtest.py --symbol EURUSD --days 90
    python scripts/backtest.py --symbol BTCUSDT --market crypto --days 30
"""

import asyncio
import sys
import os
import argparse
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from loguru import logger
from config.logging_config import setup_logging
from src.connectors.mt5_connector import MT5Connector
from src.connectors.binance_connector import BinanceConnector
from src.strategy.multi_timeframe import MultiTimeframeAnalyzer
from src.ai.classifier import TradeClassifier
from src.risk.risk_manager import RiskManager
from config.settings import settings


async def run_backtest(symbol: str, market: str, days: int):
    logger.info(f"Backtesting {symbol} ({market}) over {days} days")

    connector = MT5Connector() if market == "forex" else BinanceConnector()
    await connector.connect()

    # Fetch data
    h1_df = await connector.get_ohlcv(symbol, "H1", count=days * 24)
    m15_df = await connector.get_ohlcv(symbol, "M15", count=days * 96)
    m5_df = await connector.get_ohlcv(symbol, "M5", count=min(days * 288, 500))

    if any(df.empty for df in [h1_df, m15_df, m5_df]):
        logger.error("Could not fetch data for backtest")
        return

    analyzer = MultiTimeframeAnalyzer()
    classifier = TradeClassifier()
    risk = RiskManager()

    signals_generated = 0
    signals_valid = 0
    trades_simulated = []

    # Walk-forward through M5 candles
    window = 100
    for i in range(window, len(m5_df)):
        try:
            h1_slice = h1_df.iloc[max(0, i // 12 - 200): i // 12]
            m15_slice = m15_df.iloc[max(0, i // 3 - 200): i // 3]
            m5_slice = m5_df.iloc[max(0, i - 100): i]

            if len(m5_slice) < 30:
                continue

            signal = await analyzer.analyse(symbol, market, h1_slice, m15_slice, m5_slice)
            if not signal.valid:
                continue

            signals_generated += 1
            confidence = classifier.predict_confidence(signal)
            if confidence < settings.min_confidence:
                continue

            signals_valid += 1
            if signal.entry_price and signal.stop_loss and signal.tp1:
                # Simulate trade outcome based on future prices
                future = m5_df.iloc[i: i + 50]
                entry = signal.entry_price
                sl = signal.stop_loss
                tp3 = signal.tp3 or signal.tp1

                outcome = None
                for _, bar in future.iterrows():
                    if signal.direction == "bullish":
                        if bar["low"] <= sl:
                            outcome = "loss"
                            pnl = -(entry - sl)
                            break
                        if bar["high"] >= tp3:
                            outcome = "win"
                            pnl = tp3 - entry
                            break
                    else:
                        if bar["high"] >= sl:
                            outcome = "loss"
                            pnl = -(sl - entry)
                            break
                        if bar["low"] <= tp3:
                            outcome = "win"
                            pnl = entry - tp3
                            break

                if outcome:
                    trades_simulated.append({
                        "time": m5_df.iloc[i]["open_time"],
                        "symbol": symbol,
                        "direction": signal.direction,
                        "confidence": confidence,
                        "outcome": outcome,
                        "pnl_pct": pnl / entry if entry > 0 else 0,
                    })
        except Exception as e:
            pass

    # ─── Print Results ────────────────────────────────────────────────────────
    print(f"\n{'='*50}")
    print(f"BACKTEST RESULTS: {symbol} — {days} days")
    print(f"{'='*50}")
    print(f"Signals generated:   {signals_generated}")
    print(f"Signals after filter:{signals_valid}")
    print(f"Trades simulated:    {len(trades_simulated)}")

    if trades_simulated:
        wins = [t for t in trades_simulated if t["outcome"] == "win"]
        losses = [t for t in trades_simulated if t["outcome"] == "loss"]
        win_rate = len(wins) / len(trades_simulated)
        avg_pnl = np.mean([t["pnl_pct"] for t in trades_simulated])
        avg_conf = np.mean([t["confidence"] for t in trades_simulated])

        print(f"\nWin rate:            {win_rate:.2%}")
        print(f"Avg P&L (%):         {avg_pnl:.4%}")
        print(f"Avg AI Confidence:   {avg_conf:.2%}")
        print(f"Profit factor:       {sum(t['pnl_pct'] for t in wins) / abs(sum(t['pnl_pct'] for t in losses) or 1):.2f}")
    print(f"{'='*50}\n")

    await connector.disconnect()


if __name__ == "__main__":
    setup_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="EURUSD")
    parser.add_argument("--market", default="forex", choices=["forex", "crypto"])
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    asyncio.run(run_backtest(args.symbol, args.market, args.days))
