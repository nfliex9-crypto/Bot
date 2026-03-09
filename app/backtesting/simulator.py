"""
Market Simulator.

Replays historical candles bar-by-bar and simulates realistic
execution conditions:
  - Spread (symbol-specific, variable)
  - Slippage (random ± N pips based on volatility)
  - Commission (per-lot flat fee)
  - Partial fills (optional)
  - Price gap simulation for stop-loss jumps

The simulator feeds data one candle at a time to the BacktestEngine,
ensuring no lookahead bias.
"""
import random
from dataclasses import dataclass, field
from typing import Iterator, List, Optional, Tuple
import pandas as pd
import numpy as np


# Default spreads (pips)
DEFAULT_SPREADS = {
    "EURUSD": 0.8, "GBPUSD": 1.0, "USDJPY": 0.7, "USDCHF": 1.0,
    "AUDUSD": 0.9, "USDCAD": 1.0, "NZDUSD": 1.2, "GBPJPY": 1.8,
    "EURJPY": 1.2, "BTCUSDT": 5.0, "ETHUSDT": 2.0, "BNBUSDT": 2.0,
    "SOLUSDT": 1.5, "XRPUSDT": 1.0,
}

# Pip size per symbol
PIP_SIZES = {
    "USDJPY": 0.01, "EURJPY": 0.01, "GBPJPY": 0.01, "AUDJPY": 0.01,
}


@dataclass
class SimulatedBar:
    """A single candle with execution-ready prices."""
    symbol: str
    time: pd.Timestamp
    open: float
    high: float
    low: float
    close: float
    volume: float
    timeframe: str

    # Execution prices (adjusted for spread + slippage)
    buy_price: float = 0.0    # ask
    sell_price: float = 0.0   # bid
    spread_pips: float = 0.0


@dataclass
class ExecutionResult:
    success: bool
    filled_price: float
    slippage_pips: float
    spread_pips: float
    commission: float
    error: Optional[str] = None


class MarketSimulator:
    """
    Simulates realistic market execution for backtesting.

    Features:
    - Symbol-specific spread table (with volatility scaling)
    - Random slippage proportional to ATR
    - Commission per round trip
    - Partial fill simulation
    - Gap-through stop loss detection
    """

    def __init__(
        self,
        spread_multiplier: float = 1.0,       # Scale all spreads
        slippage_factor: float = 0.3,          # Slippage as fraction of ATR
        commission_per_lot: float = 3.5,       # USD per lot (round trip)
        enable_gaps: bool = True,              # Simulate price gaps (weekends/news)
        random_seed: Optional[int] = 42,
    ):
        self.spread_multiplier = spread_multiplier
        self.slippage_factor = slippage_factor
        self.commission_per_lot = commission_per_lot
        self.enable_gaps = enable_gaps
        self._rng = np.random.default_rng(random_seed)

    def iter_bars(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        warmup: int = 50,
    ) -> Iterator[Tuple[int, SimulatedBar, pd.DataFrame]]:
        """
        Iterate over bars, yielding (index, simulated_bar, history_slice).
        The history_slice contains only bars up to and including the current bar
        (no lookahead).

        Starts at `warmup` to allow indicators to initialise.
        """
        base_spread = DEFAULT_SPREADS.get(symbol, 1.5) * self.spread_multiplier
        pip_size = PIP_SIZES.get(symbol, 0.0001) if "USDT" not in symbol else 1.0

        for i in range(warmup, len(df)):
            row = df.iloc[i]
            hist = df.iloc[: i + 1]

            # Variable spread (widens during high volatility)
            atr = self._estimate_atr(hist, 14)
            vol_factor = min(1.0 + (atr / (row["close"] * 0.001 + 1e-10)) * 0.5, 3.0)
            spread = base_spread * vol_factor
            spread_price = spread * pip_size

            buy_price = float(row["close"]) + spread_price / 2
            sell_price = float(row["close"]) - spread_price / 2

            bar = SimulatedBar(
                symbol=symbol,
                time=row["time"],
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row.get("volume", 0)),
                timeframe=timeframe,
                buy_price=buy_price,
                sell_price=sell_price,
                spread_pips=spread,
            )
            yield i, bar, hist

    def simulate_entry(
        self,
        direction: str,
        intended_price: float,
        bar: SimulatedBar,
        lot_size: float,
    ) -> ExecutionResult:
        """
        Simulate a market order fill.

        Returns actual fill price with slippage and commission.
        """
        pip_size = PIP_SIZES.get(bar.symbol, 0.0001) if "USDT" not in bar.symbol else 1.0
        atr = abs(bar.high - bar.low)
        max_slippage = atr * self.slippage_factor
        slippage = float(self._rng.uniform(0, max_slippage))

        if direction == "long":
            # Pay the ask + slippage
            filled = bar.buy_price + slippage
        else:
            # Fill at bid - slippage
            filled = bar.sell_price - slippage

        slippage_pips = slippage / (pip_size + 1e-10)
        commission = self.commission_per_lot * lot_size

        return ExecutionResult(
            success=True,
            filled_price=filled,
            slippage_pips=round(slippage_pips, 2),
            spread_pips=bar.spread_pips,
            commission=commission,
        )

    def check_sl_tp(
        self,
        direction: str,
        entry: float,
        stop_loss: float,
        take_profit: float,
        bar: SimulatedBar,
        lot_size: float = 0.01,
        pip_value: float = 10.0,
    ) -> Optional[Tuple[str, float, float]]:
        """
        Check if the bar triggers SL or TP.
        Returns (reason, exit_price, pnl) or None.

        Handles gap-through (price jumps past SL without touching it exactly).
        """
        pip_size = PIP_SIZES.get(bar.symbol, 0.0001) if "USDT" not in bar.symbol else 1.0

        if direction == "long":
            # Gap-through SL (open below SL)
            if self.enable_gaps and bar.open <= stop_loss:
                exit_p = bar.open  # fill at open (gap fill)
                pnl = self._calc_pnl("long", entry, exit_p, lot_size, pip_size, pip_value)
                return "stop_loss_gap", exit_p, pnl

            if bar.low <= stop_loss:
                exit_p = stop_loss
                pnl = self._calc_pnl("long", entry, exit_p, lot_size, pip_size, pip_value)
                return "stop_loss", exit_p, pnl

            if bar.high >= take_profit:
                exit_p = take_profit
                pnl = self._calc_pnl("long", entry, exit_p, lot_size, pip_size, pip_value)
                return "take_profit", exit_p, pnl
        else:
            if self.enable_gaps and bar.open >= stop_loss:
                exit_p = bar.open
                pnl = self._calc_pnl("short", entry, exit_p, lot_size, pip_size, pip_value)
                return "stop_loss_gap", exit_p, pnl

            if bar.high >= stop_loss:
                exit_p = stop_loss
                pnl = self._calc_pnl("short", entry, exit_p, lot_size, pip_size, pip_value)
                return "stop_loss", exit_p, pnl

            if bar.low <= take_profit:
                exit_p = take_profit
                pnl = self._calc_pnl("short", entry, exit_p, lot_size, pip_size, pip_value)
                return "take_profit", exit_p, pnl

        return None

    def _calc_pnl(
        self,
        direction: str,
        entry: float,
        exit: float,
        lot_size: float,
        pip_size: float,
        pip_value: float,
    ) -> float:
        if direction == "long":
            pips = (exit - entry) / pip_size
        else:
            pips = (entry - exit) / pip_size
        return pips * pip_value * lot_size - self.commission_per_lot * lot_size

    def _estimate_atr(self, df: pd.DataFrame, period: int) -> float:
        if len(df) < 2:
            return 0.001
        tr = []
        closes = df["close"].values
        highs = df["high"].values
        lows = df["low"].values
        for i in range(1, min(period + 1, len(df))):
            tr.append(max(
                highs[-i] - lows[-i],
                abs(highs[-i] - closes[-i - 1]),
                abs(lows[-i] - closes[-i - 1]),
            ))
        return float(np.mean(tr)) if tr else 0.001

    def get_symbol_spread(self, symbol: str) -> float:
        return DEFAULT_SPREADS.get(symbol, 1.5) * self.spread_multiplier
