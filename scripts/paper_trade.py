"""
Start the bot in paper trading mode.
Overrides .env TRADING_MODE setting to 'paper' for safety.

Usage:
    python scripts/paper_trade.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force paper mode before imports
os.environ["TRADING_MODE"] = "paper"

from src.main import main

if __name__ == "__main__":
    sys.argv.append("--with-api")
    main()
