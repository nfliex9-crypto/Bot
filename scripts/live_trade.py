"""
Start the bot in LIVE trading mode.
⚠️  WARNING: This script places REAL orders with REAL money.
    Only use after thorough paper trading validation.

Usage:
    python scripts/live_trade.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("\n" + "=" * 60)
print("  ⚠️  LIVE TRADING MODE")
print("  Real orders will be placed.")
print("  Ensure broker credentials are set in .env")
print("=" * 60)

confirm = input("\nType 'CONFIRM LIVE TRADING' to proceed: ").strip()
if confirm != "CONFIRM LIVE TRADING":
    print("Aborted.")
    sys.exit(0)

os.environ["TRADING_MODE"] = "live"

from src.main import main

if __name__ == "__main__":
    sys.argv.append("--with-api")
    main()
