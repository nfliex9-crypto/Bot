"""
Automated strategy discovery CLI.

Examples:
    python scripts/discover_strategies.py --data-file ./data/BTCUSDT_M5.csv
    python scripts/discover_strategies.py --use-synthetic --n-strategies 240
"""
import argparse
import os
import sys
from typing import Optional

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.discovery import DiscoveryConfig, StrategyDiscoveryEngine


def generate_synthetic_ohlcv(
    n_bars: int = 12000,
    timeframe_minutes: int = 5,
    seed: int = 42,
    base_price: float = 1.10,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range(end=pd.Timestamp.now(tz="UTC"), periods=n_bars, freq=f"{timeframe_minutes}min")

    prices = [base_price]
    regime = "trend_up"
    for i in range(1, n_bars):
        if i % int(rng.integers(250, 700)) == 0:
            regime = rng.choice(["trend_up", "trend_down", "range"])
        if regime == "trend_up":
            step = rng.normal(0.00015, 0.0007)
        elif regime == "trend_down":
            step = rng.normal(-0.00015, 0.0007)
        else:
            step = rng.normal(0.0, 0.00035)
        prices.append(max(0.0001, prices[-1] + step))

    rows = []
    for i, close in enumerate(prices):
        open_price = prices[i - 1] if i > 0 else close
        spread = abs(rng.normal(0.00008, 0.00003))
        wick_up = abs(rng.normal(0.00025, 0.00012))
        wick_dn = abs(rng.normal(0.00025, 0.00012))
        high = max(open_price, close) + wick_up
        low = max(0.0001, min(open_price, close) - wick_dn)
        rows.append(
            {
                "time": dates[i],
                "open": open_price,
                "high": high + spread * 0.5,
                "low": low - spread * 0.5,
                "close": close,
                "volume": float(rng.integers(100, 8000)),
            }
        )
    return pd.DataFrame(rows)


def load_ohlcv_csv(path: str, time_col: str = "time") -> pd.DataFrame:
    df = pd.read_csv(path)
    if time_col not in df.columns:
        if "timestamp" in df.columns:
            time_col = "timestamp"
        else:
            raise ValueError(f"Could not find '{time_col}' column in {path}")

    df = df.rename(columns={time_col: "time"})
    expected = ["time", "open", "high", "low", "close", "volume"]
    missing = set(expected) - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {sorted(missing)}")
    return df[expected]


def main():
    parser = argparse.ArgumentParser(description="Automated Strategy Discovery Engine")
    parser.add_argument("--data-file", type=str, default=None, help="Path to OHLCV CSV")
    parser.add_argument("--time-col", type=str, default="time", help="CSV time column name")
    parser.add_argument("--n-strategies", type=int, default=240, help="Strategies to generate (>=200)")
    parser.add_argument("--top-k", type=int, default=5, help="Number of top strategies to export")
    parser.add_argument("--output-dir", type=str, default="outputs/strategy_discovery")
    parser.add_argument("--initial-capital", type=float, default=3000.0)
    parser.add_argument("--use-synthetic", action="store_true", help="Use synthetic OHLCV data")
    args = parser.parse_args()

    if not args.use_synthetic and not args.data_file:
        raise ValueError("Provide --data-file or use --use-synthetic")
    if args.n_strategies < 200:
        raise ValueError("--n-strategies must be >= 200")

    if args.use_synthetic:
        df = generate_synthetic_ohlcv()
        source = "synthetic"
    else:
        df = load_ohlcv_csv(args.data_file, args.time_col)
        source = args.data_file

    cfg = DiscoveryConfig(initial_capital=args.initial_capital)
    engine = StrategyDiscoveryEngine(cfg)
    result = engine.run_discovery(
        ohlcv=df,
        n_strategies=args.n_strategies,
        top_k=args.top_k,
        output_dir=args.output_dir,
    )

    print("\n" + "=" * 80)
    print("AUTOMATED STRATEGY DISCOVERY COMPLETE")
    print("=" * 80)
    print(f"Data source:          {source}")
    print(f"Candidates generated: {result['total_candidates']}")
    print(f"Survivors:            {result['survivors']}")
    print(f"Top selected:         {result['top_selected']}")
    print(f"Report directory:     {result['output_dir']}")
    print(f"Best module path:     {result['best_module_path']}")
    print("-" * 80)

    top_strategies = result.get("top_strategies", [])
    for i, item in enumerate(top_strategies, start=1):
        spec = item["strategy"]
        test = item["test"]
        print(
            f"{i}. {spec['name']} [{spec['strategy_id']}] | "
            f"Sharpe={test['sharpe_ratio']:.3f} PF={test['profit_factor']:.3f} "
            f"DD={test['max_drawdown']:.3%} Win={test['win_rate']:.2%}"
        )
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
