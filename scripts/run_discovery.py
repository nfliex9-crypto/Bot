#!/usr/bin/env python3
"""
Strategy Discovery Engine — CLI runner.

Usage:
    python scripts/run_discovery.py
    python scripts/run_discovery.py --candles 10000 --strategies 300
    python scripts/run_discovery.py --seed 123 --top 10
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.discovery.backtest import BacktestConfig
from app.discovery.engine import DiscoveryEngine


def main():
    parser = argparse.ArgumentParser(
        description="Automated Strategy Discovery Engine",
    )
    parser.add_argument(
        "--candles", type=int, default=20000,
        help="Number of OHLCV candles to generate (default: 20000)",
    )
    parser.add_argument(
        "--strategies", type=int, default=200,
        help="Minimum number of strategies to generate (default: 200)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--top", type=int, default=5,
        help="Number of top strategies to export (default: 5)",
    )
    parser.add_argument(
        "--balance", type=float, default=10000.0,
        help="Initial balance for backtesting (default: 10000)",
    )
    parser.add_argument(
        "--output", type=str, default="output/discovery",
        help="Output directory for reports (default: output/discovery)",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress progress output",
    )

    args = parser.parse_args()

    bt_cfg = BacktestConfig(
        initial_balance=args.balance,
    )

    engine = DiscoveryEngine(
        n_candles=args.candles,
        n_strategies=args.strategies,
        seed=args.seed,
        bt_cfg=bt_cfg,
        output_dir=args.output,
        verbose=not args.quiet,
    )

    report = engine.run(top_n=args.top)

    if report.total_ranked == 0:
        print("\nNo strategies survived the pipeline. Try:")
        print("  - Increasing --candles for more data")
        print("  - Adjusting filter thresholds")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
