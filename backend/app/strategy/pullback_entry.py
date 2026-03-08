"""
Pullback Entry Model

After a BOS or liquidity sweep, this model identifies optimal pullback entries
into the new trend direction using Fibonacci retracements, order blocks,
and momentum confirmation.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional

from app.strategy.indicators import (
    calculate_atr, calculate_rsi, calculate_ema,
    calculate_stochastic, identify_order_blocks
)
from app.strategy.liquidity_sweep import LiquiditySweep
from app.strategy.break_of_structure import StructureBreak


@dataclass
class TradeSetup:
    direction: str  # "long" or "short"
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    risk_reward_ratio: float
    confidence: float  # 0.0 to 1.0
    strategy_name: str
    timeframe: str
    symbol: str
    details: dict = field(default_factory=dict)
    timestamp: Optional[pd.Timestamp] = None


class PullbackEntryModel:
    """Identifies pullback entries after structural breaks or liquidity sweeps."""

    def __init__(
        self,
        fib_entry_zone: tuple = (0.5, 0.786),
        min_rr_ratio: float = 2.0,
        rsi_oversold: float = 35,
        rsi_overbought: float = 65,
        atr_period: int = 14,
        atr_sl_multiplier: float = 1.5,
    ):
        self.fib_entry_zone = fib_entry_zone
        self.min_rr_ratio = min_rr_ratio
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.atr_period = atr_period
        self.atr_sl_multiplier = atr_sl_multiplier

    def find_entries(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        sweep: Optional[LiquiditySweep] = None,
        bos: Optional[StructureBreak] = None,
    ) -> list[TradeSetup]:
        if len(df) < 50:
            return []

        setups = []
        atr = calculate_atr(df, self.atr_period)
        rsi = calculate_rsi(df["close"])
        ema_20 = calculate_ema(df["close"], 20)
        stoch_k, stoch_d = calculate_stochastic(df)
        order_blocks = identify_order_blocks(df)

        if bos:
            setup = self._evaluate_bos_pullback(
                df, bos, atr, rsi, ema_20, stoch_k, order_blocks, symbol, timeframe
            )
            if setup:
                setups.append(setup)

        if sweep:
            setup = self._evaluate_sweep_entry(
                df, sweep, atr, rsi, ema_20, stoch_k, order_blocks, symbol, timeframe
            )
            if setup:
                setups.append(setup)

        if not sweep and not bos:
            setup = self._evaluate_standalone_pullback(
                df, atr, rsi, ema_20, stoch_k, order_blocks, symbol, timeframe
            )
            if setup:
                setups.append(setup)

        return [s for s in setups if s.risk_reward_ratio >= self.min_rr_ratio]

    def _evaluate_bos_pullback(
        self,
        df: pd.DataFrame,
        bos: StructureBreak,
        atr: pd.Series,
        rsi: pd.Series,
        ema_20: pd.Series,
        stoch_k: pd.Series,
        order_blocks: list,
        symbol: str,
        timeframe: str,
    ) -> Optional[TradeSetup]:
        idx = len(df) - 1
        current_atr = atr.iloc[idx]
        if pd.isna(current_atr) or current_atr == 0:
            return None

        current_close = df["close"].iloc[idx]
        current_rsi = rsi.iloc[idx] if not pd.isna(rsi.iloc[idx]) else 50

        if bos.direction == "bullish":
            swing_low = df["low"].iloc[max(0, bos.break_candle_index - 20):bos.break_candle_index].min()
            swing_high = bos.broken_level
            fib_range = swing_high - swing_low

            entry_zone_top = swing_high - self.fib_entry_zone[0] * fib_range
            entry_zone_bottom = swing_high - self.fib_entry_zone[1] * fib_range

            in_entry_zone = entry_zone_bottom <= current_close <= entry_zone_top
            rsi_condition = current_rsi < self.rsi_overbought
            above_ema = current_close > ema_20.iloc[idx] if not pd.isna(ema_20.iloc[idx]) else True

            ob_confluence = self._check_order_block_confluence(
                order_blocks, current_close, "bullish"
            )

            if in_entry_zone and rsi_condition:
                entry = current_close
                sl = entry - current_atr * self.atr_sl_multiplier
                risk = entry - sl

                tp1 = entry + risk * 1.5
                tp2 = entry + risk * 2.5
                tp3 = entry + risk * 4.0

                confidence = self._calculate_confidence(
                    bos_strength=bos.strength,
                    is_choch=bos.is_change_of_character,
                    in_zone=in_entry_zone,
                    rsi_ok=rsi_condition,
                    ema_ok=above_ema,
                    ob_confluence=ob_confluence,
                    volume_spike=False,
                )

                rr = (tp2 - entry) / risk if risk > 0 else 0

                return TradeSetup(
                    direction="long",
                    entry_price=round(entry, 5),
                    stop_loss=round(sl, 5),
                    take_profit_1=round(tp1, 5),
                    take_profit_2=round(tp2, 5),
                    take_profit_3=round(tp3, 5),
                    risk_reward_ratio=round(rr, 2),
                    confidence=round(confidence, 3),
                    strategy_name="BOS_Pullback_Long",
                    timeframe=timeframe,
                    symbol=symbol,
                    details={
                        "bos_level": bos.broken_level,
                        "bos_strength": bos.strength,
                        "is_choch": bos.is_change_of_character,
                        "entry_zone": [entry_zone_bottom, entry_zone_top],
                        "rsi": current_rsi,
                        "atr": current_atr,
                        "ob_confluence": ob_confluence,
                    },
                    timestamp=df["timestamp"].iloc[idx] if "timestamp" in df.columns else None,
                )

        elif bos.direction == "bearish":
            swing_high = df["high"].iloc[max(0, bos.break_candle_index - 20):bos.break_candle_index].max()
            swing_low = bos.broken_level
            fib_range = swing_high - swing_low

            entry_zone_bottom = swing_low + self.fib_entry_zone[0] * fib_range
            entry_zone_top = swing_low + self.fib_entry_zone[1] * fib_range

            in_entry_zone = entry_zone_bottom <= current_close <= entry_zone_top
            rsi_condition = current_rsi > self.rsi_oversold
            below_ema = current_close < ema_20.iloc[idx] if not pd.isna(ema_20.iloc[idx]) else True

            ob_confluence = self._check_order_block_confluence(
                order_blocks, current_close, "bearish"
            )

            if in_entry_zone and rsi_condition:
                entry = current_close
                sl = entry + current_atr * self.atr_sl_multiplier
                risk = sl - entry

                tp1 = entry - risk * 1.5
                tp2 = entry - risk * 2.5
                tp3 = entry - risk * 4.0

                confidence = self._calculate_confidence(
                    bos_strength=bos.strength,
                    is_choch=bos.is_change_of_character,
                    in_zone=in_entry_zone,
                    rsi_ok=rsi_condition,
                    ema_ok=below_ema,
                    ob_confluence=ob_confluence,
                    volume_spike=False,
                )

                rr = (entry - tp2) / risk if risk > 0 else 0

                return TradeSetup(
                    direction="short",
                    entry_price=round(entry, 5),
                    stop_loss=round(sl, 5),
                    take_profit_1=round(tp1, 5),
                    take_profit_2=round(tp2, 5),
                    take_profit_3=round(tp3, 5),
                    risk_reward_ratio=round(rr, 2),
                    confidence=round(confidence, 3),
                    strategy_name="BOS_Pullback_Short",
                    timeframe=timeframe,
                    symbol=symbol,
                    details={
                        "bos_level": bos.broken_level,
                        "bos_strength": bos.strength,
                        "is_choch": bos.is_change_of_character,
                        "entry_zone": [entry_zone_bottom, entry_zone_top],
                        "rsi": current_rsi,
                        "atr": current_atr,
                        "ob_confluence": ob_confluence,
                    },
                    timestamp=df["timestamp"].iloc[idx] if "timestamp" in df.columns else None,
                )

        return None

    def _evaluate_sweep_entry(
        self,
        df: pd.DataFrame,
        sweep: LiquiditySweep,
        atr: pd.Series,
        rsi: pd.Series,
        ema_20: pd.Series,
        stoch_k: pd.Series,
        order_blocks: list,
        symbol: str,
        timeframe: str,
    ) -> Optional[TradeSetup]:
        idx = len(df) - 1
        current_atr = atr.iloc[idx]
        if pd.isna(current_atr) or current_atr == 0:
            return None

        current_close = df["close"].iloc[idx]
        current_rsi = rsi.iloc[idx] if not pd.isna(rsi.iloc[idx]) else 50

        if sweep.direction == "bullish":
            entry = current_close
            sl = entry - current_atr * self.atr_sl_multiplier
            risk = entry - sl

            tp1 = entry + risk * 1.5
            tp2 = entry + risk * 2.5
            tp3 = entry + risk * 4.0

            rsi_ok = current_rsi < self.rsi_overbought
            ob_confluence = self._check_order_block_confluence(order_blocks, current_close, "bullish")

            confidence = self._calculate_sweep_confidence(
                sweep.rejection_strength, sweep.volume_spike, sweep.wick_ratio,
                rsi_ok, ob_confluence,
            )
            rr = (tp2 - entry) / risk if risk > 0 else 0

            return TradeSetup(
                direction="long",
                entry_price=round(entry, 5),
                stop_loss=round(sl, 5),
                take_profit_1=round(tp1, 5),
                take_profit_2=round(tp2, 5),
                take_profit_3=round(tp3, 5),
                risk_reward_ratio=round(rr, 2),
                confidence=round(confidence, 3),
                strategy_name="LiqSweep_Long",
                timeframe=timeframe,
                symbol=symbol,
                details={
                    "sweep_level": sweep.sweep_level,
                    "rejection_strength": sweep.rejection_strength,
                    "volume_spike": sweep.volume_spike,
                    "wick_ratio": sweep.wick_ratio,
                    "rsi": current_rsi,
                    "atr": current_atr,
                },
                timestamp=df["timestamp"].iloc[idx] if "timestamp" in df.columns else None,
            )

        elif sweep.direction == "bearish":
            entry = current_close
            sl = entry + current_atr * self.atr_sl_multiplier
            risk = sl - entry

            tp1 = entry - risk * 1.5
            tp2 = entry - risk * 2.5
            tp3 = entry - risk * 4.0

            rsi_ok = current_rsi > self.rsi_oversold
            ob_confluence = self._check_order_block_confluence(order_blocks, current_close, "bearish")

            confidence = self._calculate_sweep_confidence(
                sweep.rejection_strength, sweep.volume_spike, sweep.wick_ratio,
                rsi_ok, ob_confluence,
            )
            rr = (entry - tp2) / risk if risk > 0 else 0

            return TradeSetup(
                direction="short",
                entry_price=round(entry, 5),
                stop_loss=round(sl, 5),
                take_profit_1=round(tp1, 5),
                take_profit_2=round(tp2, 5),
                take_profit_3=round(tp3, 5),
                risk_reward_ratio=round(rr, 2),
                confidence=round(confidence, 3),
                strategy_name="LiqSweep_Short",
                timeframe=timeframe,
                symbol=symbol,
                details={
                    "sweep_level": sweep.sweep_level,
                    "rejection_strength": sweep.rejection_strength,
                    "volume_spike": sweep.volume_spike,
                    "wick_ratio": sweep.wick_ratio,
                    "rsi": current_rsi,
                    "atr": current_atr,
                },
                timestamp=df["timestamp"].iloc[idx] if "timestamp" in df.columns else None,
            )

        return None

    def _evaluate_standalone_pullback(
        self,
        df: pd.DataFrame,
        atr: pd.Series,
        rsi: pd.Series,
        ema_20: pd.Series,
        stoch_k: pd.Series,
        order_blocks: list,
        symbol: str,
        timeframe: str,
    ) -> Optional[TradeSetup]:
        """Evaluate pullback entry without a preceding BOS or sweep signal."""
        idx = len(df) - 1
        current_atr = atr.iloc[idx]
        if pd.isna(current_atr) or current_atr == 0:
            return None

        current_close = df["close"].iloc[idx]
        current_rsi = rsi.iloc[idx] if not pd.isna(rsi.iloc[idx]) else 50
        ema_val = ema_20.iloc[idx] if not pd.isna(ema_20.iloc[idx]) else current_close

        ema_50 = calculate_ema(df["close"], 50)
        ema_50_val = ema_50.iloc[idx] if not pd.isna(ema_50.iloc[idx]) else current_close

        uptrend = current_close > ema_50_val and ema_val > ema_50_val
        downtrend = current_close < ema_50_val and ema_val < ema_50_val

        if uptrend and current_rsi < 45 and current_close <= ema_val * 1.005:
            entry = current_close
            sl = entry - current_atr * self.atr_sl_multiplier
            risk = entry - sl
            tp1 = entry + risk * 1.5
            tp2 = entry + risk * 2.5
            tp3 = entry + risk * 4.0
            rr = (tp2 - entry) / risk if risk > 0 else 0

            return TradeSetup(
                direction="long",
                entry_price=round(entry, 5),
                stop_loss=round(sl, 5),
                take_profit_1=round(tp1, 5),
                take_profit_2=round(tp2, 5),
                take_profit_3=round(tp3, 5),
                risk_reward_ratio=round(rr, 2),
                confidence=0.45,
                strategy_name="EMA_Pullback_Long",
                timeframe=timeframe,
                symbol=symbol,
                details={"rsi": current_rsi, "atr": current_atr, "ema_20": ema_val},
                timestamp=df["timestamp"].iloc[idx] if "timestamp" in df.columns else None,
            )

        elif downtrend and current_rsi > 55 and current_close >= ema_val * 0.995:
            entry = current_close
            sl = entry + current_atr * self.atr_sl_multiplier
            risk = sl - entry
            tp1 = entry - risk * 1.5
            tp2 = entry - risk * 2.5
            tp3 = entry - risk * 4.0
            rr = (entry - tp2) / risk if risk > 0 else 0

            return TradeSetup(
                direction="short",
                entry_price=round(entry, 5),
                stop_loss=round(sl, 5),
                take_profit_1=round(tp1, 5),
                take_profit_2=round(tp2, 5),
                take_profit_3=round(tp3, 5),
                risk_reward_ratio=round(rr, 2),
                confidence=0.45,
                strategy_name="EMA_Pullback_Short",
                timeframe=timeframe,
                symbol=symbol,
                details={"rsi": current_rsi, "atr": current_atr, "ema_20": ema_val},
                timestamp=df["timestamp"].iloc[idx] if "timestamp" in df.columns else None,
            )

        return None

    def _check_order_block_confluence(
        self, order_blocks: list, price: float, direction: str
    ) -> bool:
        for ob in order_blocks[-10:]:
            if ob["type"] == direction and ob["low"] <= price <= ob["high"]:
                return True
        return False

    def _calculate_confidence(
        self,
        bos_strength: float,
        is_choch: bool,
        in_zone: bool,
        rsi_ok: bool,
        ema_ok: bool,
        ob_confluence: bool,
        volume_spike: bool,
    ) -> float:
        score = 0.0
        score += bos_strength * 0.25
        score += 0.15 if is_choch else 0.05
        score += 0.15 if in_zone else 0.0
        score += 0.10 if rsi_ok else 0.0
        score += 0.10 if ema_ok else 0.0
        score += 0.15 if ob_confluence else 0.0
        score += 0.10 if volume_spike else 0.0
        return min(1.0, score)

    def _calculate_sweep_confidence(
        self,
        rejection_strength: float,
        volume_spike: bool,
        wick_ratio: float,
        rsi_ok: bool,
        ob_confluence: bool,
    ) -> float:
        score = 0.0
        score += rejection_strength * 0.30
        score += 0.15 if volume_spike else 0.0
        score += wick_ratio * 0.20
        score += 0.15 if rsi_ok else 0.0
        score += 0.20 if ob_confluence else 0.0
        return min(1.0, score)
