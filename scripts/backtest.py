"""
Backtesting Script.

Runs the full strategy (MTF analysis + AI scoring) on historical OHLCV data
to evaluate performance before live deployment.

Usage:
    python scripts/backtest.py --symbol EURUSD --days 90
    python scripts/backtest.py --symbol BTCUSDT --market crypto --days 30
    python scripts/backtest.py --all-symbols --days 60
"""
import sys
import os
import asyncio
import argparse
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np

from app.config import settings
from app.core.strategy.multi_timeframe import MultiTimeframeAnalyzer
from app.core.ai.classifier import TradeClassifier
from app.core.risk_manager import RiskManager
from app.core.session_filter import SessionFilter
from app.utils.indicators import add_all_indicators
from app.utils.logger import get_logger

logger = get_logger("backtest")

UTC = timezone.utc


def generate_ohlcv(
    n_candles: int = 1000,
    timeframe_minutes: int = 5,
    seed: int = 42,
    symbol: str = "EURUSD",
) -> pd.DataFrame:
    """
    Generate synthetic OHLCV data with realistic price behavior
    (trending, ranging, and reversal patterns).
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range(
        end=pd.Timestamp.now(tz="UTC"),
        periods=n_candles,
        freq=f"{timeframe_minutes}min",
    )

    # Generate price with regime changes
    price = 1.1000 if symbol.endswith("USD") and not symbol.startswith("USD") else 50000.0
    volatility = 0.0002 if "USD" in symbol and "BTC" not in symbol else 20.0

    prices = [price]
    regime = "trend_up"
    regime_length = 0

    for i in range(1, n_candles):
        regime_length += 1

        # Switch regime randomly
        if regime_length > rng.integers(30, 80):
            regime = rng.choice(["trend_up", "trend_down", "ranging"])
            regime_length = 0

        if regime == "trend_up":
            change = rng.normal(volatility * 0.3, volatility)
        elif regime == "trend_down":
            change = rng.normal(-volatility * 0.3, volatility)
        else:
            change = rng.normal(0, volatility * 0.5)

        prices.append(max(prices[-1] + change, 0.0001))

    # Build OHLCV
    rows = []
    for i, (dt, close) in enumerate(zip(dates, prices)):
        spread = rng.uniform(0.3, 1.0) * volatility
        high_extra = rng.uniform(0, 2.0) * volatility
        low_extra = rng.uniform(0, 2.0) * volatility
        open_price = prices[i - 1] if i > 0 else close
        rows.append({
            "time": dt,
            "open": open_price,
            "high": max(open_price, close) + high_extra,
            "low": min(open_price, close) - low_extra,
            "close": close,
            "volume": float(rng.integers(100, 10000)),
        })

    return pd.DataFrame(rows)


class BacktestEngine:
    """
    Simple event-driven backtesting engine.
    """

    def __init__(
        self,
        initial_balance: float = 3000.0,
        risk_per_trade: float = 0.0075,
        commission: float = 0.0002,  # 2 pips round trip
    ):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.risk_per_trade = risk_per_trade
        self.commission = commission

        self.trades: List[Dict] = []
        self.equity_curve: List[float] = [initial_balance]
        self.mtf_analyzer = MultiTimeframeAnalyzer()
        self.classifier = TradeClassifier()
        self.session_filter = SessionFilter()
        self.risk_manager = RiskManager(
            account_balance=initial_balance,
            risk_per_trade=risk_per_trade,
            max_drawdown=0.20,  # Wider for backtesting
            max_trades_per_session=5,
        )

        self._open_trades: List[Dict] = []
        self._scan_count = 0

    def run(
        self,
        symbol: str,
        h1_df: pd.DataFrame,
        m15_df: pd.DataFrame,
        m5_df: pd.DataFrame,
        warmup_bars: int = 100,
    ) -> dict:
        """
        Run backtest across the M5 dataframe.
        """
        logger.info(f"Running backtest: {symbol} | {len(m5_df)} M5 bars")

        total_bars = len(m5_df)

        for i in range(warmup_bars, total_bars):
            current_time = m5_df.iloc[i]["time"]
            current_price = m5_df.iloc[i]["close"]

            # Update open trade P&L
            self._update_open_trades(current_price, i)

            # Skip if too many open trades
            if len(self._open_trades) >= settings.MAX_TRADES_PER_SESSION:
                continue

            # Only scan every 3 bars (equivalent to 15-minute interval on M5)
            if i % 3 != 0:
                continue

            # Get slices up to current bar
            h1_slice = self._get_slice(h1_df, current_time, 100)
            m15_slice = self._get_slice(m15_df, current_time, 100)
            m5_slice = m5_df.iloc[max(0, i - 100): i + 1].copy()

            if len(h1_slice) < 50 or len(m15_slice) < 30 or len(m5_slice) < 20:
                continue

            # MTF analysis
            try:
                mtf = self.mtf_analyzer.analyze(symbol, h1_slice, m15_slice, m5_slice)
            except Exception as e:
                continue

            if not mtf.tradeable or mtf.m5_entry is None:
                continue

            # AI scoring
            prediction = self.classifier.predict(h1_slice, m15_slice, m5_slice, mtf)
            if not prediction.should_trade:
                continue

            # Session check
            session = self.session_filter.get_current_session(
                current_time.to_pydatetime() if hasattr(current_time, "to_pydatetime") else current_time
            )
            if not session.is_active:
                continue

            # Risk check
            risk_status = self.risk_manager.check_risk_limits()
            if not risk_status.can_trade:
                continue

            # Enter trade
            entry = mtf.m5_entry
            risk_amount = self.balance * self.risk_per_trade
            sl_distance = abs(entry.entry_price - entry.stop_loss)

            if sl_distance <= 0:
                continue

            self._open_trade(
                symbol=symbol,
                direction=entry.direction,
                entry_price=current_price,  # Use current close as entry
                stop_loss=entry.stop_loss,
                take_profit_1=entry.take_profit_1,
                take_profit_2=entry.take_profit_2,
                take_profit_3=entry.take_profit_3,
                risk_amount=risk_amount,
                confidence=prediction.confidence,
                bar_idx=i,
                timestamp=current_time,
            )

            self._scan_count += 1

        # Close any remaining open trades at last price
        last_price = m5_df.iloc[-1]["close"]
        for trade in list(self._open_trades):
            self._close_trade(trade, last_price, "end_of_data")

        return self._compute_results(symbol)

    def _get_slice(self, df: pd.DataFrame, current_time, n: int) -> pd.DataFrame:
        """Get up to n bars before current_time."""
        mask = df["time"] <= current_time
        return df[mask].tail(n).copy()

    def _open_trade(self, **kwargs):
        """Open a new trade."""
        trade = dict(**kwargs)
        trade["unrealized_pnl"] = 0.0
        trade["closed"] = False
        trade["exit_price"] = None
        trade["exit_reason"] = None
        trade["tp1_hit"] = False
        self._open_trades.append(trade)
        logger.debug(
            f"BT Open: {kwargs['symbol']} {kwargs['direction']} "
            f"@ {kwargs['entry_price']:.5f}"
        )

    def _update_open_trades(self, current_price: float, bar_idx: int):
        """Update and potentially close open trades."""
        for trade in list(self._open_trades):
            direction = trade["direction"]
            entry = trade["entry_price"]
            sl = trade["stop_loss"]
            tp1 = trade["take_profit_1"]
            tp2 = trade.get("take_profit_2")
            tp3 = trade.get("take_profit_3")

            # Stop loss
            if (direction == "long" and current_price <= sl) or \
               (direction == "short" and current_price >= sl):
                self._close_trade(trade, sl, "stop_loss")
                continue

            # TP3 full close
            if tp3 and ((direction == "long" and current_price >= tp3) or
                        (direction == "short" and current_price <= tp3)):
                self._close_trade(trade, tp3, "tp3")
                continue

            # TP2
            if tp2 and not trade.get("tp2_hit") and \
               ((direction == "long" and current_price >= tp2) or
                    (direction == "short" and current_price <= tp2)):
                trade["tp2_hit"] = True
                partial_pnl = self._calc_pnl(direction, entry, tp2, trade["risk_amount"] * 0.33)
                self.balance += partial_pnl - self.commission * trade["risk_amount"]
                self.risk_manager.record_trade_pnl(partial_pnl)

            # TP1 + break-even
            if not trade["tp1_hit"] and \
               ((direction == "long" and current_price >= tp1) or
                    (direction == "short" and current_price <= tp1)):
                trade["tp1_hit"] = True
                partial_pnl = self._calc_pnl(direction, entry, tp1, trade["risk_amount"] * 0.33)
                self.balance += partial_pnl - self.commission * trade["risk_amount"]
                self.risk_manager.record_trade_pnl(partial_pnl)
                # Move SL to break-even
                trade["stop_loss"] = entry

    def _close_trade(self, trade: dict, exit_price: float, reason: str):
        """Close a trade and record results."""
        if trade in self._open_trades:
            self._open_trades.remove(trade)

        remaining_pct = 0.34 if (trade.get("tp1_hit") and trade.get("tp2_hit")) else \
                        0.67 if trade.get("tp1_hit") else 1.0

        pnl = self._calc_pnl(
            trade["direction"],
            trade["entry_price"],
            exit_price,
            trade["risk_amount"] * remaining_pct,
        )
        commission = self.commission * trade["risk_amount"] * remaining_pct
        net_pnl = pnl - commission

        self.balance += net_pnl
        self.equity_curve.append(self.balance)
        self.risk_manager.record_trade_pnl(net_pnl)

        trade["exit_price"] = exit_price
        trade["exit_reason"] = reason
        trade["pnl"] = net_pnl
        trade["closed"] = True
        self.trades.append(trade)

        logger.debug(
            f"BT Close: {trade['symbol']} {trade['direction']} "
            f"@ {exit_price:.5f} pnl={net_pnl:+.2f} reason={reason}"
        )

    def _calc_pnl(self, direction: str, entry: float, exit: float, risk: float) -> float:
        """Calculate P&L based on price movement."""
        if direction == "long":
            return (exit - entry) / entry * risk * 100
        else:
            return (entry - exit) / entry * risk * 100

    def _compute_results(self, symbol: str) -> dict:
        """Compute backtest statistics."""
        if not self.trades:
            return {"symbol": symbol, "total_trades": 0, "message": "No trades executed"}

        pnls = [t.get("pnl", 0) for t in self.trades]
        winners = [p for p in pnls if p > 0]
        losers = [p for p in pnls if p <= 0]
        total_pnl = sum(pnls)

        # Max drawdown
        curve = np.array(self.equity_curve)
        peak = np.maximum.accumulate(curve)
        drawdown = (peak - curve) / (peak + 1e-10)
        max_dd = float(drawdown.max())

        win_rate = len(winners) / len(pnls) if pnls else 0
        profit_factor = abs(sum(winners) / sum(losers)) if losers and sum(losers) != 0 else float("inf")

        by_reason = {}
        for t in self.trades:
            r = t.get("exit_reason", "unknown")
            if r not in by_reason:
                by_reason[r] = {"count": 0, "pnl": 0.0}
            by_reason[r]["count"] += 1
            by_reason[r]["pnl"] = round(by_reason[r]["pnl"] + t.get("pnl", 0), 2)

        return {
            "symbol": symbol,
            "initial_balance": self.initial_balance,
            "final_balance": round(self.balance, 2),
            "total_return": round((self.balance - self.initial_balance) / self.initial_balance * 100, 2),
            "total_trades": len(self.trades),
            "winning_trades": len(winners),
            "losing_trades": len(losers),
            "win_rate": round(win_rate, 4),
            "win_rate_pct": f"{win_rate * 100:.1f}%",
            "total_pnl": round(total_pnl, 2),
            "avg_win": round(sum(winners) / len(winners), 2) if winners else 0,
            "avg_loss": round(sum(losers) / len(losers), 2) if losers else 0,
            "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "∞",
            "max_drawdown": round(max_dd, 4),
            "max_drawdown_pct": f"{max_dd * 100:.1f}%",
            "exit_reasons": by_reason,
        }


def main():
    parser = argparse.ArgumentParser(description="AI Trading Bot Backtester")
    parser.add_argument("--symbol", type=str, default="EURUSD")
    parser.add_argument("--market", type=str, default="forex", choices=["forex", "crypto"])
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--all-symbols", action="store_true")
    parser.add_argument("--balance", type=float, default=3000.0)
    args = parser.parse_args()

    symbols = (
        settings.forex_symbol_list + settings.crypto_symbol_list
        if args.all_symbols
        else [args.symbol]
    )

    print("\n" + "=" * 60)
    print(f"AI TRADING BOT - BACKTESTER")
    print(f"Balance: ${args.balance:,.2f} | Period: {args.days} days")
    print("=" * 60)

    all_results = []

    for symbol in symbols:
        n_m5 = args.days * 24 * 12  # M5 candles per day
        n_m15 = args.days * 24 * 4
        n_h1 = args.days * 24

        # Generate synthetic price data
        seed = sum(ord(c) for c in symbol)
        m5_df = generate_ohlcv(n_m5, 5, seed, symbol)
        m15_df = generate_ohlcv(n_m15, 15, seed + 1, symbol)
        h1_df = generate_ohlcv(n_h1, 60, seed + 2, symbol)

        engine = BacktestEngine(initial_balance=args.balance)

        try:
            result = engine.run(symbol, h1_df, m15_df, m5_df, warmup_bars=100)
        except Exception as e:
            logger.error(f"Backtest error for {symbol}: {e}")
            continue

        all_results.append(result)

        print(f"\n{symbol}:")
        print(f"  Trades:       {result.get('total_trades', 0)}")
        if result.get("total_trades", 0) > 0:
            print(f"  Win Rate:     {result.get('win_rate_pct', 'N/A')}")
            print(f"  Profit Factor:{result.get('profit_factor', 'N/A')}")
            print(f"  Total P&L:    ${result.get('total_pnl', 0):+.2f}")
            print(f"  Total Return: {result.get('total_return', 0):+.2f}%")
            print(f"  Max Drawdown: {result.get('max_drawdown_pct', 'N/A')}")
            print(f"  Final Balance:${result.get('final_balance', 0):,.2f}")

    if len(all_results) > 1:
        total_pnl = sum(r.get("total_pnl", 0) for r in all_results)
        total_trades = sum(r.get("total_trades", 0) for r in all_results)
        print(f"\n{'=' * 60}")
        print(f"PORTFOLIO SUMMARY:")
        print(f"  Total Trades: {total_trades}")
        print(f"  Total P&L:    ${total_pnl:+.2f}")
        print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
