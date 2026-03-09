"""
Vectorised backtesting engine for the strategy discovery pipeline.

Design principles:
  * Strict chronological order — no future data.
  * Realistic costs: configurable spread, commission, and ATR-based slippage.
  * Single-position per strategy (close before re-entering).
  * SL/TP checked on high/low (intrabar), indicator exits on close.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.discovery.indicators import add_all_discovery_indicators
from app.discovery.strategy_config import Condition, StrategyConfig


@dataclass
class BacktestConfig:
    initial_balance: float = 10_000.0
    cost_per_trade_r: float = 0.07      # total round-trip cost in R-units (spread + commission + slippage)
    slippage_atr_mult: float = 0.02     # slippage applied to fills = ATR × mult
    warmup_bars: int = 210              # skip first N bars for indicator warm-up
    max_open_trades: int = 1
    risk_pct: float = 0.01              # per-trade risk (overridden by strategy)


# ── condition evaluation ─────────────────────────────────────


def _resolve(df: pd.DataFrame, operand: Any) -> pd.Series:
    """Resolve an operand to a Series (column lookup or scalar broadcast)."""
    if isinstance(operand, str):
        if operand in df.columns:
            return df[operand]
        raise KeyError(f"Column '{operand}' not found in DataFrame")
    return pd.Series(operand, index=df.index, dtype=float)


def evaluate_condition(df: pd.DataFrame, cond: Condition) -> pd.Series:
    left = _resolve(df, cond.left)
    right = _resolve(df, cond.right)

    if cond.op == ">":
        return left > right
    if cond.op == "<":
        return left < right
    if cond.op == ">=":
        return left >= right
    if cond.op == "<=":
        return left <= right
    if cond.op == "==":
        return left == right
    if cond.op == "cross_above":
        return (left > right) & (left.shift(1) <= right.shift(1))
    if cond.op == "cross_below":
        return (left < right) & (left.shift(1) >= right.shift(1))
    raise ValueError(f"Unknown operator: {cond.op}")


def evaluate_conditions(df: pd.DataFrame, conditions: List[Condition]) -> pd.Series:
    """AND-combine all conditions; returns boolean Series."""
    if not conditions:
        return pd.Series(False, index=df.index)
    result = pd.Series(True, index=df.index)
    for cond in conditions:
        result = result & evaluate_condition(df, cond)
    return result


# ── derived columns for special strategy families ────────────


def _add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add shifted / derived columns referenced by generator conditions."""
    new_cols: dict = {}

    for col in list(df.columns):
        if col.startswith("highest_") or col.startswith("lowest_"):
            prev_name = f"__prev_{col}"
            if prev_name not in df.columns:
                new_cols[prev_name] = df[col].shift(1)

    for col in list(df.columns):
        if col.startswith("atr_"):
            period = col.split("_")[1]
            sma_col = f"sma_atr_{period}"
            if sma_col not in df.columns and sma_col not in new_cols:
                new_cols[sma_col] = df[col].rolling(20).mean()
            sma_series = new_cols.get(sma_col, df.get(sma_col))
            if sma_series is not None:
                for mult_x10 in [12, 15, 20]:
                    derived = f"__atr_sma_{period}_x_{mult_x10}"
                    if derived not in df.columns:
                        new_cols[derived] = sma_series * (mult_x10 / 10.0)

    if new_cols:
        extra = pd.DataFrame(new_cols, index=df.index)
        df = pd.concat([df, extra], axis=1)

    return df


# ── backtest runner ──────────────────────────────────────────


@dataclass
class _OpenTrade:
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_amount: float
    bar_idx: int


def run_backtest(
    strategy: StrategyConfig,
    df: pd.DataFrame,
    cfg: Optional[BacktestConfig] = None,
) -> Tuple[List[Dict], List[float]]:
    """
    Run a single strategy backtest on pre-indicator'd DataFrame *df*.

    Returns (trades, equity_curve).
    Each trade dict has keys: direction, entry_price, exit_price,
    pnl, r_multiple, exit_reason, bar_entry, bar_exit.
    """
    if cfg is None:
        cfg = BacktestConfig()

    risk_pct = strategy.risk_pct or cfg.risk_pct
    balance = cfg.initial_balance
    equity_curve: List[float] = [balance]
    trades: List[Dict] = []
    open_trade: Optional[_OpenTrade] = None

    atr_col = "atr_14"
    if atr_col not in df.columns:
        return trades, equity_curve

    try:
        long_signals = evaluate_conditions(df, strategy.long_entry)
        short_signals = evaluate_conditions(df, strategy.short_entry)
        long_exit_signals = evaluate_conditions(df, strategy.long_exit) if strategy.long_exit else pd.Series(False, index=df.index)
        short_exit_signals = evaluate_conditions(df, strategy.short_exit) if strategy.short_exit else pd.Series(False, index=df.index)
    except (KeyError, ValueError):
        return trades, equity_curve

    closes = df["close"].values
    highs = df["high"].values
    lows = df["low"].values
    atrs = df[atr_col].values
    long_sig = long_signals.values
    short_sig = short_signals.values
    long_ex = long_exit_signals.values
    short_ex = short_exit_signals.values

    n = len(df)

    for i in range(cfg.warmup_bars, n):
        atr_i = atrs[i]
        if np.isnan(atr_i) or atr_i <= 0:
            atr_i = abs(closes[i]) * 0.001

        slippage = atr_i * cfg.slippage_atr_mult

        # ── manage open trade ────────────────────────────────
        if open_trade is not None:
            hit_sl = False
            hit_tp = False
            exit_price = 0.0
            exit_reason = ""

            if open_trade.direction == "long":
                if lows[i] <= open_trade.stop_loss:
                    hit_sl = True
                    exit_price = open_trade.stop_loss - slippage
                    exit_reason = "stop_loss"
                elif highs[i] >= open_trade.take_profit:
                    hit_tp = True
                    exit_price = open_trade.take_profit - slippage
                    exit_reason = "take_profit"
                elif long_ex[i]:
                    exit_price = closes[i] - slippage
                    exit_reason = "indicator_exit"
            else:
                if highs[i] >= open_trade.stop_loss:
                    hit_sl = True
                    exit_price = open_trade.stop_loss + slippage
                    exit_reason = "stop_loss"
                elif lows[i] <= open_trade.take_profit:
                    hit_tp = True
                    exit_price = open_trade.take_profit + slippage
                    exit_reason = "take_profit"
                elif short_ex[i]:
                    exit_price = closes[i] + slippage
                    exit_reason = "indicator_exit"

            if hit_sl or hit_tp or exit_reason:
                sl_dist = abs(open_trade.entry_price - open_trade.stop_loss)
                if sl_dist <= 0:
                    sl_dist = atr_i * strategy.sl_atr_mult

                if open_trade.direction == "long":
                    r_multiple = (exit_price - open_trade.entry_price) / sl_dist
                else:
                    r_multiple = (open_trade.entry_price - exit_price) / sl_dist

                pnl_dollar = open_trade.risk_amount * r_multiple - open_trade.risk_amount * cfg.cost_per_trade_r

                trades.append({
                    "direction": open_trade.direction,
                    "entry_price": open_trade.entry_price,
                    "exit_price": exit_price,
                    "pnl": pnl_dollar,
                    "r_multiple": r_multiple,
                    "exit_reason": exit_reason,
                    "bar_entry": open_trade.bar_idx,
                    "bar_exit": i,
                })

                balance += pnl_dollar
                equity_curve.append(balance)
                open_trade = None

        # ── check for new entry ──────────────────────────────
        if open_trade is None and i < n - 1:
            direction = None
            if long_sig[i]:
                direction = "long"
            elif short_sig[i]:
                direction = "short"

            if direction is not None:
                entry_price = closes[i]
                if direction == "long":
                    entry_price += slippage
                else:
                    entry_price -= slippage

                sl_distance = atr_i * strategy.sl_atr_mult
                if direction == "long":
                    stop_loss = entry_price - sl_distance
                    take_profit = entry_price + sl_distance * strategy.tp_rr
                else:
                    stop_loss = entry_price + sl_distance
                    take_profit = entry_price - sl_distance * strategy.tp_rr

                risk_amount = balance * risk_pct

                open_trade = _OpenTrade(
                    direction=direction,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    risk_amount=risk_amount,
                    bar_idx=i,
                )

    # close dangling trade at last bar
    if open_trade is not None:
        exit_price = closes[-1]
        sl_dist = abs(open_trade.entry_price - open_trade.stop_loss)
        if sl_dist <= 0:
            sl_dist = abs(open_trade.entry_price) * 0.001

        if open_trade.direction == "long":
            r_multiple = (exit_price - open_trade.entry_price) / sl_dist
        else:
            r_multiple = (open_trade.entry_price - exit_price) / sl_dist

        pnl_dollar = open_trade.risk_amount * r_multiple

        trades.append({
            "direction": open_trade.direction,
            "entry_price": open_trade.entry_price,
            "exit_price": exit_price,
            "pnl": pnl_dollar,
            "r_multiple": r_multiple,
            "exit_reason": "end_of_data",
            "bar_entry": open_trade.bar_idx,
            "bar_exit": n - 1,
        })
        balance += pnl_dollar
        equity_curve.append(balance)

    return trades, equity_curve


def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Compute indicators + derived columns once, reuse across strategies."""
    df = add_all_discovery_indicators(df)
    df = _add_derived_columns(df)
    return df
