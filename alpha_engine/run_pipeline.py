#!/usr/bin/env python3
"""
Alpha Discovery Engine — Pipeline Runner

Usage:
    python -m alpha_engine.run_pipeline                         # Full pipeline with defaults
    python -m alpha_engine.run_pipeline --mode demo             # Demo with relaxed thresholds
    python -m alpha_engine.run_pipeline --symbols SPY QQQ IWM   # Specific symbols
    python -m alpha_engine.run_pipeline --provider yahoo        # Use Yahoo Finance data
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from .config import EngineConfig, ValidationConfig
from .pipeline.orchestrator import AlphaDiscoveryPipeline


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def build_demo_config() -> EngineConfig:
    """Config with relaxed thresholds for demonstration with synthetic data."""
    return EngineConfig(
        validation=ValidationConfig(
            min_sharpe=0.3,
            min_sortino=0.3,
            max_drawdown=0.40,
            min_profit_factor=1.05,
            min_trades=20,
            min_oos_sharpe=0.1,
            deflated_sharpe_threshold=0.50,
            n_monte_carlo_sims=200,
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Alpha Discovery Engine Pipeline")
    parser.add_argument("--mode", choices=["production", "demo"], default="demo",
                        help="Run mode: production (strict) or demo (relaxed)")
    parser.add_argument("--symbols", nargs="+", default=None,
                        help="Symbols to process")
    parser.add_argument("--provider", default="synthetic",
                        help="Data provider (synthetic, yahoo)")
    parser.add_argument("--max-strategies", type=int, default=15,
                        help="Maximum strategies to select for portfolio")
    parser.add_argument("--log-level", default="INFO",
                        help="Logging level")

    args = parser.parse_args()
    setup_logging(args.log_level)

    if args.mode == "demo":
        config = build_demo_config()
        symbols = args.symbols or [f"SYN_{i:03d}" for i in range(8)]
    else:
        config = EngineConfig()
        symbols = args.symbols or config.data.base_symbols

    pipeline = AlphaDiscoveryPipeline(config)
    result = pipeline.run(
        symbols=symbols,
        provider=args.provider,
        max_strategies=args.max_strategies,
    )

    print("\n" + "=" * 70)
    print("PIPELINE SUMMARY")
    print("=" * 70)
    print(json.dumps(result.summary(), indent=2, default=str))

    if result.portfolio and result.portfolio.weights:
        print("\nPORTFOLIO WEIGHTS:")
        for sid, w in sorted(result.portfolio.weights.items(), key=lambda x: -abs(x[1])):
            print(f"  {sid}: {w:+.1%}")

    if result.selection_result and not result.selection_result.rankings.empty:
        print("\nTOP STRATEGIES:")
        print(result.selection_result.rankings.to_string(index=False))


if __name__ == "__main__":
    main()
