"""
Backtesting script — runs the strategy on historical data to validate performance.
"""

from __future__ import annotations

import sys
sys.path.insert(0, ".")

import numpy as np
import pandas as pd
from loguru import logger

from app.ai.classifier import TradeClassifier
from app.analysis.market_structure import analyse_structure
from app.analysis.indicators import atr, ema, rsi
from app.strategy.liquidity_sweep import detect_liquidity_sweep
from app.strategy.bos_detector import confirm_bos
from app.strategy.pullback_entry import find_pullback_entry


def generate_synthetic_ohlcv(n: int = 2000, seed: int = 42) -> pd.DataFrame:
    """Generate realistic synthetic OHLCV data for backtesting."""
    rng = np.random.RandomState(seed)
    prices = [1.1000]

    for _ in range(n - 1):
        change = rng.normal(0, 0.0005)
        prices.append(prices[-1] + change)

    df = pd.DataFrame()
    df["close"] = prices
    df["open"] = df["close"].shift(1).fillna(df["close"])
    df["high"] = df[["open", "close"]].max(axis=1) + abs(rng.normal(0, 0.0003, n))
    df["low"] = df[["open", "close"]].min(axis=1) - abs(rng.normal(0, 0.0003, n))
    df["volume"] = rng.randint(100, 10000, n).astype(float)
    df["timestamp"] = pd.date_range("2024-01-01", periods=n, freq="5min", tz="UTC")

    return df


def run_backtest():
    logger.info("Running backtest on synthetic data...")

    df = generate_synthetic_ohlcv(5000)
    classifier = TradeClassifier()
    classifier.load_or_train()

    trades = []
    window = 200

    for i in range(window, len(df) - 1):
        chunk = df.iloc[i - window : i + 1].reset_index(drop=True)

        sweeps = detect_liquidity_sweep(chunk)
        if not sweeps:
            continue

        structure = analyse_structure(chunk)
        for sweep in sweeps:
            bos = confirm_bos(structure, structure.bias, sweep["direction"])
            if bos is None:
                continue

            entry = find_pullback_entry(chunk, sweep["direction"])
            if entry is None:
                continue

            atr_val = float(atr(chunk, 14).iloc[-1])
            if atr_val == 0:
                continue

            sl_dist = atr_val * 1.5
            entry_price = entry["entry_price"]

            if sweep["direction"] == "long":
                sl = entry_price - sl_dist
                tp1 = entry_price + sl_dist
                tp2 = entry_price + sl_dist * 1.5
            else:
                sl = entry_price + sl_dist
                tp1 = entry_price - sl_dist
                tp2 = entry_price - sl_dist * 1.5

            # Check next candle for outcome
            if i + 1 < len(df):
                next_close = df["close"].iloc[i + 1]
                if sweep["direction"] == "long":
                    pnl = next_close - entry_price
                else:
                    pnl = entry_price - next_close

                trades.append({
                    "direction": sweep["direction"],
                    "entry": entry_price,
                    "exit": next_close,
                    "pnl": pnl,
                    "win": pnl > 0,
                })

    if not trades:
        logger.info("No trades generated in backtest")
        return

    trade_df = pd.DataFrame(trades)
    wins = trade_df["win"].sum()
    total = len(trade_df)
    total_pnl = trade_df["pnl"].sum()

    logger.info(f"Backtest Results:")
    logger.info(f"  Total trades: {total}")
    logger.info(f"  Win rate: {wins/total*100:.1f}%")
    logger.info(f"  Total PnL: {total_pnl:.5f}")
    logger.info(f"  Avg PnL: {trade_df['pnl'].mean():.5f}")
    logger.info(f"  Best trade: {trade_df['pnl'].max():.5f}")
    logger.info(f"  Worst trade: {trade_df['pnl'].min():.5f}")


if __name__ == "__main__":
    run_backtest()
