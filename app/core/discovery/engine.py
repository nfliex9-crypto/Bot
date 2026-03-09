"""
Automated strategy discovery engine.

This module generates strategy candidates, backtests them chronologically,
filters by robustness criteria, performs walk-forward validation, ranks
survivors, and exports both reports and a trading-engine-compatible module
for the best strategy.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.utils.logger import get_logger

UTC = timezone.utc
logger = get_logger("strategy_discovery")


@dataclass
class DiscoveryConfig:
    initial_capital: float = 3000.0
    spread_bps: float = 1.2
    commission_bps: float = 0.8
    atr_slippage_mult: float = 0.04
    warmup_bars: int = 120
    training_ratio: float = 0.60
    validation_ratio: float = 0.20
    min_trades_per_period: int = 12

    # Hard filter requirements
    min_profit_factor: float = 1.5
    min_sharpe: float = 1.0
    max_drawdown: float = 0.15


@dataclass
class StrategySpec:
    strategy_id: str
    name: str
    primary_logic: str
    confirmation_logic: str
    entry_description: str
    exit_description: str
    stop_loss_rule: str
    take_profit_rule: str
    position_sizing_rule: str
    indicators: List[str]
    parameters: Dict[str, float]


@dataclass
class TradeRecord:
    entry_time: str
    exit_time: str
    direction: str
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float
    quantity: float
    gross_pnl: float
    net_pnl: float
    r_multiple: float
    bars_held: int
    exit_reason: str


@dataclass
class PerformanceMetrics:
    total_trades: int
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    avg_r_multiple: float
    trade_frequency: float
    total_return: float
    ending_equity: float


@dataclass
class EvaluatedStrategy:
    spec: StrategySpec
    train: PerformanceMetrics
    validation: PerformanceMetrics
    test: PerformanceMetrics
    passed_filters: bool
    passed_out_of_sample: bool
    consistency: float
    complexity: float
    composite_score: float = 0.0


def _safe_float(value: float, fallback: float = 0.0) -> float:
    if value is None:
        return fallback
    if isinstance(value, (float, np.floating)) and (np.isnan(value) or np.isinf(value)):
        return fallback
    return float(value)


def _max_drawdown_from_curve(equity_curve: np.ndarray) -> float:
    if len(equity_curve) == 0:
        return 0.0
    peak = np.maximum.accumulate(equity_curve)
    dd = (peak - equity_curve) / (peak + 1e-12)
    return float(np.max(dd))


def _rolling_vwap(df: pd.DataFrame, window: int = 30) -> pd.Series:
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    pv = typical * df["volume"].fillna(0.0)
    return pv.rolling(window=window).sum() / df["volume"].rolling(window=window).sum().replace(0, np.nan)


class StrategyDiscoveryEngine:
    """
    End-to-end strategy discovery.

    The engine deliberately biases toward simple two-layer rules:
    primary setup + optional confirmation. This helps reduce overfitting.
    """

    LOGIC_FAMILIES = (
        "trend_following",
        "breakout",
        "mean_reversion",
        "volatility_expansion",
        "liquidity_sweep",
        "market_structure_break",
        "momentum",
    )

    ALLOWED_INDICATORS = (
        "EMA",
        "SMA",
        "RSI",
        "ATR",
        "MACD",
        "Bollinger Bands",
        "VWAP",
    )

    def __init__(self, config: Optional[DiscoveryConfig] = None):
        self.config = config or DiscoveryConfig()

    def run_discovery(
        self,
        ohlcv: pd.DataFrame,
        n_strategies: int = 240,
        top_k: int = 5,
        output_dir: str = "outputs/strategy_discovery",
    ) -> Dict:
        df = self._prepare_dataframe(ohlcv)
        train_df, validation_df, test_df = self._walk_forward_split(df)
        evaluated: List[EvaluatedStrategy] = []
        ranked: List[EvaluatedStrategy] = []
        candidate_counter = 0
        seeds = [42, 314, 2718, 9001]

        for attempt, seed in enumerate(seeds, start=1):
            id_start = candidate_counter + 1
            candidates = self.generate_strategies(
                n_strategies=n_strategies,
                seed=seed,
                id_start=id_start,
            )
            candidate_counter += len(candidates)
            logger.info(
                f"Strategy discovery pass {attempt}/{len(seeds)} | candidates={len(candidates)} "
                f"bars(train/val/test)=({len(train_df)}/{len(validation_df)}/{len(test_df)})"
            )

            for idx, spec in enumerate(candidates, start=1):
                if idx % 25 == 0:
                    logger.info(
                        f"Evaluating strategy {idx}/{len(candidates)} in pass {attempt}"
                    )

                train_metrics, _ = self._backtest_strategy(spec, train_df)
                val_metrics, _ = self._backtest_strategy(spec, validation_df)
                test_metrics, _ = self._backtest_strategy(spec, test_df)

                passed_train_val = self._passes_filters(train_metrics) and self._passes_filters(val_metrics)
                passed_oos = self._passes_filters(test_metrics)

                consistency = self._compute_consistency(train_metrics, val_metrics, test_metrics)
                complexity = self._compute_complexity(spec)

                evaluated.append(
                    EvaluatedStrategy(
                        spec=spec,
                        train=train_metrics,
                        validation=val_metrics,
                        test=test_metrics,
                        passed_filters=passed_train_val,
                        passed_out_of_sample=passed_oos,
                        consistency=consistency,
                        complexity=complexity,
                    )
                )

            survivors = [e for e in evaluated if e.passed_filters and e.passed_out_of_sample]
            ranked = self._rank_survivors(survivors)
            if len(ranked) >= top_k:
                break

        top = ranked[:top_k]

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        self._export_reports(
            output_dir=output_path,
            evaluated=evaluated,
            survivors=ranked,
            top=top,
            n_strategies=candidate_counter,
            periods={
                "training_bars": len(train_df),
                "validation_bars": len(validation_df),
                "test_bars": len(test_df),
            },
        )

        best_module_path = None
        if top:
            best_module_path = self._generate_trading_module(top[0], Path("app/core/strategy/discovered_auto.py"))

        logger.info(
            f"Discovery completed | survivors={len(ranked)} top_selected={len(top)} "
            f"module={'created' if best_module_path else 'not_created'}"
        )

        return {
            "total_candidates": candidate_counter,
            "survivors": len(ranked),
            "top_selected": len(top),
            "top_strategies": [self._serialize_evaluated(x) for x in top],
            "best_module_path": str(best_module_path) if best_module_path else None,
            "output_dir": str(output_path),
        }

    def generate_strategies(
        self,
        n_strategies: int = 240,
        seed: int = 42,
        id_start: int = 1,
    ) -> List[StrategySpec]:
        """
        Generate strategy candidates by combining required logic families.
        """
        if n_strategies < 200:
            raise ValueError("n_strategies must be >= 200")

        rng = np.random.default_rng(seed)
        specs: List[StrategySpec] = []

        ema_pairs = [(8, 21), (9, 34), (12, 50), (20, 50), (21, 100)]
        breakout_windows = [10, 20, 30, 40]
        structure_windows = [8, 12, 20, 30]
        bb_periods = [14, 20, 26]
        bb_stds = [1.8, 2.0, 2.2]
        rsi_thresholds = [(28, 72), (30, 70), (35, 65)]
        risk_fracs = [0.0025, 0.004, 0.005, 0.0065, 0.0075, 0.009]
        sl_mults = [1.2, 1.5, 1.8, 2.2]
        rr_targets = [1.6, 2.0, 2.4, 3.0]
        max_holds = [30, 48, 72]
        confirmations = ["none"] + list(self.LOGIC_FAMILIES)

        strategy_num = id_start
        while len(specs) < n_strategies:
            primary = self.LOGIC_FAMILIES[len(specs) % len(self.LOGIC_FAMILIES)]
            confirmation = rng.choice(confirmations)
            if confirmation == primary:
                confirmation = "none"

            ema_fast, ema_slow = ema_pairs[rng.integers(0, len(ema_pairs))]
            rsi_low, rsi_high = rsi_thresholds[rng.integers(0, len(rsi_thresholds))]

            params = {
                "ema_fast": float(ema_fast),
                "ema_slow": float(ema_slow),
                "sma_period": float(rng.choice([20, 50, 100])),
                "breakout_window": float(rng.choice(breakout_windows)),
                "structure_window": float(rng.choice(structure_windows)),
                "bb_period": float(rng.choice(bb_periods)),
                "bb_std": float(rng.choice(bb_stds)),
                "rsi_low": float(rsi_low),
                "rsi_high": float(rsi_high),
                "vol_expansion_k": float(rng.choice([1.2, 1.4, 1.6, 1.8])),
                "sweep_atr_buffer": float(rng.choice([0.05, 0.1, 0.15])),
                "macd_hist_min": float(rng.choice([0.0, 0.00001, 0.00005])),
                "risk_fraction": float(rng.choice(risk_fracs)),
                "sl_atr_mult": float(rng.choice(sl_mults)),
                "tp_rr": float(rng.choice(rr_targets)),
                "max_hold_bars": float(rng.choice(max_holds)),
                "exit_on_opposite": float(rng.choice([0.0, 1.0])),
            }

            entry_desc = (
                f"Primary={primary}; confirmation={confirmation}; "
                f"EMA({ema_fast}/{ema_slow}), RSI({rsi_low}/{rsi_high}), "
                f"breakout={int(params['breakout_window'])}, structure={int(params['structure_window'])}"
            )
            exit_desc = (
                f"ATR stop x{params['sl_atr_mult']}, TP {params['tp_rr']}R, "
                f"max hold {int(params['max_hold_bars'])} bars, "
                f"opposite_exit={'on' if params['exit_on_opposite'] > 0.5 else 'off'}"
            )

            indicators = ["EMA", "SMA", "RSI", "ATR", "MACD", "Bollinger Bands", "VWAP"]
            spec = StrategySpec(
                strategy_id=f"STRAT_{strategy_num:04d}",
                name=f"{primary.replace('_', ' ').title()} {strategy_num}",
                primary_logic=primary,
                confirmation_logic=confirmation,
                entry_description=entry_desc,
                exit_description=exit_desc,
                stop_loss_rule="ATR multiple stop",
                take_profit_rule="Fixed R-multiple target",
                position_sizing_rule="Fixed fractional risk based on stop distance",
                indicators=indicators,
                parameters=params,
            )
            specs.append(spec)
            strategy_num += 1

        return specs

    def _prepare_dataframe(self, ohlcv: pd.DataFrame) -> pd.DataFrame:
        required = {"open", "high", "low", "close", "volume"}
        missing = required - set(ohlcv.columns)
        if missing:
            raise ValueError(f"OHLCV dataframe missing columns: {sorted(missing)}")

        df = ohlcv.copy()
        if "time" in df.columns:
            df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
            df = df.dropna(subset=["time"]).sort_values("time")
            df = df.set_index("time")
        elif not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("OHLCV must contain a 'time' column or DatetimeIndex.")
        else:
            if df.index.tz is None:
                df.index = df.index.tz_localize("UTC")
            else:
                df.index = df.index.tz_convert("UTC")

        for col in ("open", "high", "low", "close", "volume"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["open", "high", "low", "close"]).copy()
        df = df[~df.index.duplicated(keep="last")]

        # Indicator cache
        df["ema_8"] = df["close"].ewm(span=8, adjust=False).mean()
        df["ema_9"] = df["close"].ewm(span=9, adjust=False).mean()
        df["ema_12"] = df["close"].ewm(span=12, adjust=False).mean()
        df["ema_20"] = df["close"].ewm(span=20, adjust=False).mean()
        df["ema_21"] = df["close"].ewm(span=21, adjust=False).mean()
        df["ema_34"] = df["close"].ewm(span=34, adjust=False).mean()
        df["ema_50"] = df["close"].ewm(span=50, adjust=False).mean()
        df["ema_100"] = df["close"].ewm(span=100, adjust=False).mean()
        df["sma_20"] = df["close"].rolling(20).mean()
        df["sma_50"] = df["close"].rolling(50).mean()
        df["sma_100"] = df["close"].rolling(100).mean()

        prev_close = df["close"].shift(1)
        tr = pd.concat(
            [
                df["high"] - df["low"],
                (df["high"] - prev_close).abs(),
                (df["low"] - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        df["atr_14"] = tr.ewm(span=14, adjust=False).mean()

        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(com=13, adjust=False).mean()
        avg_loss = loss.ewm(com=13, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        df["rsi_14"] = 100 - (100 / (1 + rs))

        ema_fast = df["close"].ewm(span=12, adjust=False).mean()
        ema_slow = df["close"].ewm(span=26, adjust=False).mean()
        df["macd"] = ema_fast - ema_slow
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]
        bb_mid = df["close"].rolling(20).mean()
        bb_std = df["close"].rolling(20).std()
        df["bb_upper_20_2"] = bb_mid + 2.0 * bb_std
        df["bb_lower_20_2"] = bb_mid - 2.0 * bb_std
        df["vwap_30"] = _rolling_vwap(df, 30)

        df = df.dropna().copy()
        if len(df) < max(self.config.warmup_bars + 50, 300):
            raise ValueError("Not enough OHLCV bars after indicator warmup.")
        return df

    def _walk_forward_split(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        n = len(df)
        train_end = int(n * self.config.training_ratio)
        val_end = train_end + int(n * self.config.validation_ratio)

        train = df.iloc[:train_end].copy()
        validation = df.iloc[train_end:val_end].copy()
        test = df.iloc[val_end:].copy()

        min_bars = self.config.warmup_bars + 30
        if len(train) < min_bars or len(validation) < min_bars // 2 or len(test) < min_bars // 2:
            raise ValueError("Insufficient bars for walk-forward split.")
        return train, validation, test

    def _build_logic_signals(self, df: pd.DataFrame, logic: str, p: Dict[str, float]) -> Tuple[pd.Series, pd.Series]:
        close = df["close"]
        high = df["high"]
        low = df["low"]
        atr = df["atr_14"]
        rsi = df["rsi_14"]
        macd_hist = df["macd_hist"]

        if logic == "trend_following":
            ef = int(p["ema_fast"])
            es = int(p["ema_slow"])
            ema_fast = df[f"ema_{ef}"] if f"ema_{ef}" in df.columns else close.ewm(span=ef, adjust=False).mean()
            ema_slow = df[f"ema_{es}"] if f"ema_{es}" in df.columns else close.ewm(span=es, adjust=False).mean()
            long_signal = (ema_fast > ema_slow) & (close > ema_fast)
            short_signal = (ema_fast < ema_slow) & (close < ema_fast)
            return long_signal.fillna(False), short_signal.fillna(False)

        if logic == "breakout":
            window = int(p["breakout_window"])
            prev_high = high.rolling(window).max().shift(1)
            prev_low = low.rolling(window).min().shift(1)
            buf = p["sweep_atr_buffer"] * atr
            long_signal = close > (prev_high + buf)
            short_signal = close < (prev_low - buf)
            return long_signal.fillna(False), short_signal.fillna(False)

        if logic == "mean_reversion":
            period = int(p["bb_period"])
            stdv = p["bb_std"]
            mid = close.rolling(period).mean()
            st = close.rolling(period).std()
            upper = mid + stdv * st
            lower = mid - stdv * st
            long_signal = (close < lower) & (rsi < p["rsi_low"])
            short_signal = (close > upper) & (rsi > p["rsi_high"])
            return long_signal.fillna(False), short_signal.fillna(False)

        if logic == "volatility_expansion":
            body = (close - df["open"]).abs()
            range_ = high - low
            vol_expanded = (range_ / (atr + 1e-12)) > p["vol_expansion_k"]
            trend_ema = df["ema_20"]
            long_signal = vol_expanded & (body > atr * 0.2) & (close > trend_ema)
            short_signal = vol_expanded & (body > atr * 0.2) & (close < trend_ema)
            return long_signal.fillna(False), short_signal.fillna(False)

        if logic == "liquidity_sweep":
            window = int(p["breakout_window"])
            prev_high = high.rolling(window).max().shift(1)
            prev_low = low.rolling(window).min().shift(1)
            atr_buf = atr * p["sweep_atr_buffer"]
            long_signal = (low < (prev_low - atr_buf)) & (close > prev_low)
            short_signal = (high > (prev_high + atr_buf)) & (close < prev_high)
            return long_signal.fillna(False), short_signal.fillna(False)

        if logic == "market_structure_break":
            window = int(p["structure_window"])
            struct_high = high.rolling(window).max().shift(1)
            struct_low = low.rolling(window).min().shift(1)
            long_signal = close > struct_high
            short_signal = close < struct_low
            return long_signal.fillna(False), short_signal.fillna(False)

        if logic == "momentum":
            long_signal = (macd_hist > p["macd_hist_min"]) & (rsi > 52) & (close > df["vwap_30"])
            short_signal = (macd_hist < -p["macd_hist_min"]) & (rsi < 48) & (close < df["vwap_30"])
            return long_signal.fillna(False), short_signal.fillna(False)

        raise ValueError(f"Unknown logic: {logic}")

    def _build_entry_signals(self, df: pd.DataFrame, spec: StrategySpec) -> Tuple[pd.Series, pd.Series]:
        p = spec.parameters
        primary_long, primary_short = self._build_logic_signals(df, spec.primary_logic, p)
        if spec.confirmation_logic == "none":
            confirm_long = pd.Series(True, index=df.index)
            confirm_short = pd.Series(True, index=df.index)
        else:
            confirm_long, confirm_short = self._build_logic_signals(df, spec.confirmation_logic, p)

        # Coherence filter: trend-aware with SMA
        sma_period = int(p["sma_period"])
        sma = df[f"sma_{sma_period}"] if f"sma_{sma_period}" in df.columns else df["close"].rolling(sma_period).mean()

        long_entry = primary_long & confirm_long & (df["close"] >= sma)
        short_entry = primary_short & confirm_short & (df["close"] <= sma)
        return long_entry.fillna(False), short_entry.fillna(False)

    def _backtest_strategy(self, spec: StrategySpec, df: pd.DataFrame) -> Tuple[PerformanceMetrics, List[TradeRecord]]:
        long_signal, short_signal = self._build_entry_signals(df, spec)
        p = spec.parameters

        spread_rate = self.config.spread_bps / 10000.0
        commission_rate = self.config.commission_bps / 10000.0

        equity = self.config.initial_capital
        equity_curve = [equity]
        records: List[TradeRecord] = []
        position = None

        warmup = min(self.config.warmup_bars, max(10, len(df) // 5))
        for i in range(warmup + 1, len(df)):
            idx = df.index[i]
            bar = df.iloc[i]
            prev_signal_i = i - 1
            atr = max(_safe_float(bar["atr_14"], 0.0), 1e-10)
            slip = atr * self.config.atr_slippage_mult

            # Exit management first (strict chronology)
            if position is not None:
                position["bars_held"] += 1
                exit_price = None
                exit_reason = None

                if position["direction"] == "long":
                    stop_hit = bar["low"] <= position["stop_loss"]
                    tp_hit = bar["high"] >= position["take_profit"]
                    if stop_hit and tp_hit:
                        # Conservative tie break to avoid optimistic bias.
                        exit_price = position["stop_loss"] - slip - position["spread_half"]
                        exit_reason = "stop_and_tp_same_bar"
                    elif stop_hit:
                        exit_price = position["stop_loss"] - slip - position["spread_half"]
                        exit_reason = "stop_loss"
                    elif tp_hit:
                        exit_price = position["take_profit"] - slip - position["spread_half"]
                        exit_reason = "take_profit"

                else:  # short
                    stop_hit = bar["high"] >= position["stop_loss"]
                    tp_hit = bar["low"] <= position["take_profit"]
                    if stop_hit and tp_hit:
                        exit_price = position["stop_loss"] + slip + position["spread_half"]
                        exit_reason = "stop_and_tp_same_bar"
                    elif stop_hit:
                        exit_price = position["stop_loss"] + slip + position["spread_half"]
                        exit_reason = "stop_loss"
                    elif tp_hit:
                        exit_price = position["take_profit"] + slip + position["spread_half"]
                        exit_reason = "take_profit"

                if exit_price is None and p["exit_on_opposite"] > 0.5:
                    if position["direction"] == "long" and short_signal.iloc[prev_signal_i]:
                        exit_price = bar["open"] - slip - position["spread_half"]
                        exit_reason = "opposite_signal"
                    elif position["direction"] == "short" and long_signal.iloc[prev_signal_i]:
                        exit_price = bar["open"] + slip + position["spread_half"]
                        exit_reason = "opposite_signal"

                if exit_price is None and position["bars_held"] >= int(p["max_hold_bars"]):
                    if position["direction"] == "long":
                        exit_price = bar["close"] - slip - position["spread_half"]
                    else:
                        exit_price = bar["close"] + slip + position["spread_half"]
                    exit_reason = "time_exit"

                if exit_price is not None:
                    if position["direction"] == "long":
                        gross = (exit_price - position["entry_price"]) * position["qty"]
                    else:
                        gross = (position["entry_price"] - exit_price) * position["qty"]

                    exit_commission = abs(exit_price * position["qty"]) * commission_rate
                    net = gross - exit_commission
                    equity += net
                    equity_curve.append(equity)

                    r_multiple = net / (position["risk_cash"] + 1e-12)
                    records.append(
                        TradeRecord(
                            entry_time=position["entry_time"].isoformat(),
                            exit_time=idx.isoformat(),
                            direction=position["direction"],
                            entry_price=float(position["entry_price"]),
                            exit_price=float(exit_price),
                            stop_loss=float(position["stop_loss"]),
                            take_profit=float(position["take_profit"]),
                            quantity=float(position["qty"]),
                            gross_pnl=float(gross),
                            net_pnl=float(net),
                            r_multiple=float(r_multiple),
                            bars_held=int(position["bars_held"]),
                            exit_reason=exit_reason,
                        )
                    )
                    position = None

            # Entry only when flat
            if position is None:
                entry_dir = None
                if long_signal.iloc[prev_signal_i] and not short_signal.iloc[prev_signal_i]:
                    entry_dir = "long"
                elif short_signal.iloc[prev_signal_i] and not long_signal.iloc[prev_signal_i]:
                    entry_dir = "short"

                if entry_dir is not None:
                    spread_half = bar["open"] * spread_rate * 0.5
                    if entry_dir == "long":
                        entry_price = bar["open"] + spread_half + slip
                        stop_price = entry_price - atr * p["sl_atr_mult"]
                    else:
                        entry_price = bar["open"] - spread_half - slip
                        stop_price = entry_price + atr * p["sl_atr_mult"]

                    stop_dist = abs(entry_price - stop_price)
                    if stop_dist <= 0:
                        equity_curve.append(equity)
                        continue

                    risk_cash = max(equity * p["risk_fraction"], 0.0)
                    qty = risk_cash / stop_dist
                    if qty <= 0:
                        equity_curve.append(equity)
                        continue

                    if entry_dir == "long":
                        take_profit = entry_price + stop_dist * p["tp_rr"]
                    else:
                        take_profit = entry_price - stop_dist * p["tp_rr"]

                    entry_commission = abs(entry_price * qty) * commission_rate
                    equity -= entry_commission

                    position = {
                        "direction": entry_dir,
                        "entry_price": entry_price,
                        "stop_loss": stop_price,
                        "take_profit": take_profit,
                        "qty": qty,
                        "risk_cash": risk_cash,
                        "entry_time": idx,
                        "bars_held": 0,
                        "spread_half": spread_half,
                    }

            equity_curve.append(equity)

        # End-of-period forced close
        if position is not None:
            last = df.iloc[-1]
            atr = max(_safe_float(last["atr_14"], 0.0), 1e-10)
            slip = atr * self.config.atr_slippage_mult
            spread_half = last["close"] * (self.config.spread_bps / 10000.0) * 0.5
            if position["direction"] == "long":
                exit_price = last["close"] - slip - spread_half
                gross = (exit_price - position["entry_price"]) * position["qty"]
            else:
                exit_price = last["close"] + slip + spread_half
                gross = (position["entry_price"] - exit_price) * position["qty"]

            exit_commission = abs(exit_price * position["qty"]) * (self.config.commission_bps / 10000.0)
            net = gross - exit_commission
            equity += net
            equity_curve.append(equity)
            records.append(
                TradeRecord(
                    entry_time=position["entry_time"].isoformat(),
                    exit_time=df.index[-1].isoformat(),
                    direction=position["direction"],
                    entry_price=float(position["entry_price"]),
                    exit_price=float(exit_price),
                    stop_loss=float(position["stop_loss"]),
                    take_profit=float(position["take_profit"]),
                    quantity=float(position["qty"]),
                    gross_pnl=float(gross),
                    net_pnl=float(net),
                    r_multiple=float(net / (position["risk_cash"] + 1e-12)),
                    bars_held=int(position["bars_held"]),
                    exit_reason="end_of_period",
                )
            )

        metrics = self._compute_metrics(records, np.array(equity_curve), df.index, self.config.initial_capital)
        return metrics, records

    def _compute_metrics(
        self,
        records: List[TradeRecord],
        equity_curve: np.ndarray,
        index: pd.DatetimeIndex,
        initial_capital: float,
    ) -> PerformanceMetrics:
        if not records:
            return PerformanceMetrics(
                total_trades=0,
                win_rate=0.0,
                profit_factor=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                avg_r_multiple=0.0,
                trade_frequency=0.0,
                total_return=0.0,
                ending_equity=float(initial_capital),
            )

        net = np.array([r.net_pnl for r in records], dtype=float)
        r_mult = np.array([r.r_multiple for r in records], dtype=float)

        wins = net[net > 0]
        losses = net[net < 0]
        win_rate = float(len(wins) / len(net))
        if len(losses) == 0:
            profit_factor = 9.99
        else:
            profit_factor = float(np.sum(wins) / abs(np.sum(losses)))

        eq_series = pd.Series(equity_curve)
        returns = eq_series.pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
        ret_std = returns.std()
        if ret_std <= 1e-12:
            sharpe = 0.0
        else:
            sharpe = float((returns.mean() / ret_std) * math.sqrt(252))

        max_dd = _max_drawdown_from_curve(equity_curve)
        avg_r = float(np.mean(r_mult)) if len(r_mult) else 0.0
        total_return = float((equity_curve[-1] - initial_capital) / initial_capital)

        total_days = max((index[-1] - index[0]).total_seconds() / 86400.0, 1e-9)
        trade_frequency = float(len(records) / total_days)

        return PerformanceMetrics(
            total_trades=int(len(records)),
            win_rate=win_rate,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            avg_r_multiple=avg_r,
            trade_frequency=trade_frequency,
            total_return=total_return,
            ending_equity=float(equity_curve[-1]),
        )

    def _passes_filters(self, m: PerformanceMetrics) -> bool:
        return (
            m.total_trades >= self.config.min_trades_per_period
            and m.profit_factor > self.config.min_profit_factor
            and m.sharpe_ratio > self.config.min_sharpe
            and m.max_drawdown < self.config.max_drawdown
        )

    def _compute_consistency(
        self,
        train: PerformanceMetrics,
        validation: PerformanceMetrics,
        test: PerformanceMetrics,
    ) -> float:
        returns = np.array([train.total_return, validation.total_return, test.total_return], dtype=float)
        sharpes = np.array([train.sharpe_ratio, validation.sharpe_ratio, test.sharpe_ratio], dtype=float)

        ret_penalty = float(np.std(returns))
        sharpe_penalty = float(np.std(sharpes))
        score = 1.0 / (1.0 + 4.0 * ret_penalty + 0.4 * sharpe_penalty)
        return float(np.clip(score, 0.0, 1.0))

    def _compute_complexity(self, spec: StrategySpec) -> float:
        # Lower is simpler/better.
        extra_logic_penalty = 0.0 if spec.confirmation_logic == "none" else 0.25
        exit_penalty = 0.15 if spec.parameters.get("exit_on_opposite", 0.0) > 0.5 else 0.0
        return float(0.6 + extra_logic_penalty + exit_penalty)

    def _rank_survivors(self, survivors: List[EvaluatedStrategy]) -> List[EvaluatedStrategy]:
        if not survivors:
            return []

        sharpes = np.array([x.test.sharpe_ratio for x in survivors], dtype=float)
        pfs = np.array([x.test.profit_factor for x in survivors], dtype=float)
        dds = np.array([x.test.max_drawdown for x in survivors], dtype=float)
        consistency = np.array([x.consistency for x in survivors], dtype=float)
        complexity = np.array([x.complexity for x in survivors], dtype=float)

        def norm(v: np.ndarray, invert: bool = False) -> np.ndarray:
            v_min = np.min(v)
            v_max = np.max(v)
            if abs(v_max - v_min) < 1e-12:
                x = np.ones_like(v)
            else:
                x = (v - v_min) / (v_max - v_min)
            if invert:
                x = 1.0 - x
            return np.clip(x, 0.0, 1.0)

        sharpe_n = norm(sharpes)
        pf_n = norm(pfs)
        dd_n = norm(dds, invert=True)
        cons_n = norm(consistency)
        simple_n = norm(complexity, invert=True)

        for i, s in enumerate(survivors):
            s.composite_score = float(
                0.32 * sharpe_n[i]
                + 0.24 * pf_n[i]
                + 0.22 * dd_n[i]
                + 0.16 * cons_n[i]
                + 0.06 * simple_n[i]
            )

        survivors.sort(
            key=lambda x: (
                x.composite_score,
                x.test.sharpe_ratio,
                x.test.profit_factor,
                -x.test.max_drawdown,
                x.consistency,
            ),
            reverse=True,
        )
        return survivors

    def _serialize_evaluated(self, e: EvaluatedStrategy) -> Dict:
        return {
            "strategy": asdict(e.spec),
            "train": asdict(e.train),
            "validation": asdict(e.validation),
            "test": asdict(e.test),
            "passed_filters": e.passed_filters,
            "passed_out_of_sample": e.passed_out_of_sample,
            "consistency": e.consistency,
            "complexity": e.complexity,
            "composite_score": e.composite_score,
        }

    def _export_reports(
        self,
        output_dir: Path,
        evaluated: List[EvaluatedStrategy],
        survivors: List[EvaluatedStrategy],
        top: List[EvaluatedStrategy],
        n_strategies: int,
        periods: Dict[str, int],
    ) -> None:
        summary = {
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "generated_strategies": n_strategies,
            "evaluated_strategies": len(evaluated),
            "survivors": len(survivors),
            "top_selected": len(top),
            "filter_thresholds": {
                "profit_factor": f">{self.config.min_profit_factor}",
                "sharpe_ratio": f">{self.config.min_sharpe}",
                "max_drawdown": f"<{self.config.max_drawdown}",
                "min_trades": self.config.min_trades_per_period,
            },
            "walk_forward": periods,
        }
        (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        (output_dir / "all_survivors.json").write_text(
            json.dumps([self._serialize_evaluated(x) for x in survivors], indent=2),
            encoding="utf-8",
        )
        (output_dir / "top_5_strategies.json").write_text(
            json.dumps([self._serialize_evaluated(x) for x in top], indent=2),
            encoding="utf-8",
        )

        lines = [
            "# Strategy Discovery Report",
            "",
            f"- Generated strategies: **{n_strategies}**",
            f"- Survivors after walk-forward filter: **{len(survivors)}**",
            f"- Exported top strategies: **{len(top)}**",
            "",
            "## Top Strategies",
            "",
        ]
        for rank, e in enumerate(top, start=1):
            lines.extend(
                [
                    f"### {rank}. {e.spec.name} ({e.spec.strategy_id})",
                    f"- Primary logic: `{e.spec.primary_logic}`",
                    f"- Confirmation: `{e.spec.confirmation_logic}`",
                    f"- Composite score: `{e.composite_score:.4f}`",
                    f"- Test Sharpe: `{e.test.sharpe_ratio:.3f}`",
                    f"- Test Profit Factor: `{e.test.profit_factor:.3f}`",
                    f"- Test Max Drawdown: `{e.test.max_drawdown:.3%}`",
                    f"- Test Win Rate: `{e.test.win_rate:.2%}`",
                    f"- Avg R multiple: `{e.test.avg_r_multiple:.3f}`",
                    f"- Trade frequency (trades/day): `{e.test.trade_frequency:.3f}`",
                    f"- Entry logic: {e.spec.entry_description}",
                    f"- Exit logic: {e.spec.exit_description}",
                    f"- Parameters: `{json.dumps(e.spec.parameters, sort_keys=True)}`",
                    "",
                ]
            )

        (output_dir / "top_5_report.md").write_text("\n".join(lines), encoding="utf-8")

    def _generate_trading_module(self, best: EvaluatedStrategy, output_path: Path) -> Path:
        """
        Generate a strategy module that returns EntryResult objects so it can
        plug into current engine conventions.
        """
        spec = best.spec
        p = spec.parameters
        output_path.parent.mkdir(parents=True, exist_ok=True)

        code = f'''"""
Auto-generated strategy module from strategy discovery engine.
Generated at: {datetime.now(UTC).isoformat()}

This module is intentionally simple and deterministic.
"""
import pandas as pd
import numpy as np

from app.core.strategy.pullback_entry import EntryResult


class AutoDiscoveredStrategy:
    strategy_id = "{spec.strategy_id}"
    name = "{spec.name}"
    primary_logic = "{spec.primary_logic}"
    confirmation_logic = "{spec.confirmation_logic}"
    parameters = {json.dumps(p, sort_keys=True)}

    def _atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        prev_close = df["close"].shift(1)
        tr = pd.concat(
            [
                df["high"] - df["low"],
                (df["high"] - prev_close).abs(),
                (df["low"] - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        return tr.ewm(span=period, adjust=False).mean()

    def _rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
        avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    def _signal(self, df: pd.DataFrame) -> str:
        p = self.parameters
        close = df["close"]
        high = df["high"]
        low = df["low"]
        atr = self._atr(df)
        rsi = self._rsi(df)
        ema_fast = close.ewm(span=int(p["ema_fast"]), adjust=False).mean()
        ema_slow = close.ewm(span=int(p["ema_slow"]), adjust=False).mean()
        prev_high = high.rolling(int(p["breakout_window"])).max().shift(1)
        prev_low = low.rolling(int(p["breakout_window"])).min().shift(1)
        macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
        macd_signal = macd.ewm(span=9, adjust=False).mean()
        macd_hist = macd - macd_signal
        typical = (high + low + close) / 3.0
        vwap = (typical * df["volume"].fillna(0)).rolling(30).sum() / df["volume"].rolling(30).sum().replace(0, np.nan)

        long_cond = (
            (ema_fast > ema_slow)
            & (close > ema_fast)
            & (close > prev_high)
            & (macd_hist > p["macd_hist_min"])
            & (rsi > 52)
            & (close > vwap)
        )
        short_cond = (
            (ema_fast < ema_slow)
            & (close < ema_fast)
            & (close < prev_low)
            & (macd_hist < -p["macd_hist_min"])
            & (rsi < 48)
            & (close < vwap)
        )

        if long_cond.iloc[-1] and not short_cond.iloc[-1]:
            return "long"
        if short_cond.iloc[-1] and not long_cond.iloc[-1]:
            return "short"
        return "flat"

    def analyze(self, symbol: str, m5_df: pd.DataFrame) -> EntryResult:
        if m5_df is None or len(m5_df) < 120:
            return EntryResult(valid=False)

        df = m5_df.copy()
        atr = self._atr(df).iloc[-1]
        if pd.isna(atr) or atr <= 0:
            return EntryResult(valid=False)

        direction = self._signal(df)
        if direction == "flat":
            return EntryResult(valid=False)

        entry = float(df.iloc[-1]["close"])
        sl_atr_mult = float(self.parameters["sl_atr_mult"])
        rr = float(self.parameters["tp_rr"])
        risk = atr * sl_atr_mult

        if direction == "long":
            stop_loss = entry - risk
            tp1 = entry + risk * 1.0
            tp2 = entry + risk * min(1.5, rr)
            tp3 = entry + risk * rr
        else:
            stop_loss = entry + risk
            tp1 = entry - risk * 1.0
            tp2 = entry - risk * min(1.5, rr)
            tp3 = entry - risk * rr

        return EntryResult(
            valid=True,
            direction=direction,
            entry_price=entry,
            stop_loss=float(stop_loss),
            take_profit_1=float(tp1),
            take_profit_2=float(tp2),
            take_profit_3=float(tp3),
            risk_amount_pips=float(abs(entry - stop_loss)),
            risk_reward=float(rr),
            entry_zone_type="auto_discovered",
            atr=float(atr),
            sl_type="atr",
            confidence_boost=0.05,
        )
'''
        output_path.write_text(code, encoding="utf-8")
        return output_path

