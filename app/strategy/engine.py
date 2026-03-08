from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from loguru import logger

from app.analysis.indicators import atr
from app.analysis.market_structure import Bias
from app.analysis.multi_timeframe import MTFAnalysis
from app.strategy.bos_detector import confirm_bos
from app.strategy.liquidity_sweep import detect_liquidity_sweep
from app.strategy.pullback_entry import find_pullback_entry


@dataclass
class TradeSetup:
    symbol: str
    direction: str  # "long" | "short"
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    atr_value: float
    confidence_features: dict = field(default_factory=dict)
    notes: str = ""


class StrategyEngine:
    """
    Core strategy: Liquidity Sweep → Break of Structure → Pullback Entry

    1. Detect liquidity sweep on M5
    2. Confirm BOS on M15 aligned with H1 bias
    3. Wait for pullback entry on M5 toward EMA-21
    4. Set ATR-based SL and multi-R take-profits
    """

    def __init__(
        self,
        atr_sl_multiplier: float = 1.5,
        use_structure_sl: bool = True,
    ) -> None:
        self._atr_sl_mult = atr_sl_multiplier
        self._use_structure_sl = use_structure_sl

    def evaluate(self, mtf: MTFAnalysis) -> List[TradeSetup]:
        """Run the full strategy pipeline on a multi-timeframe analysis."""
        setups: list[TradeSetup] = []

        if not mtf.is_valid or mtf.m5_df is None or mtf.m15_df is None:
            return setups

        if mtf.h1_bias == Bias.NEUTRAL:
            return setups

        sweeps = detect_liquidity_sweep(mtf.m5_df)
        if not sweeps:
            return setups

        for sweep in sweeps:
            direction = sweep["direction"]

            bos = confirm_bos(
                mtf.m15_structure, mtf.h1_bias, direction
            )
            if bos is None:
                logger.debug(f"{mtf.symbol}: sweep {direction} but no confirming BOS")
                continue

            entry = find_pullback_entry(mtf.m5_df, direction)
            if entry is None:
                logger.debug(f"{mtf.symbol}: BOS confirmed but no pullback entry")
                continue

            setup = self._build_setup(
                symbol=mtf.symbol,
                direction=direction,
                entry=entry,
                sweep=sweep,
                mtf=mtf,
            )
            if setup:
                setups.append(setup)
                logger.info(
                    f"SETUP: {setup.symbol} {setup.direction} "
                    f"entry={setup.entry_price:.5f} SL={setup.stop_loss:.5f} "
                    f"TP1={setup.tp1:.5f} TP2={setup.tp2:.5f} TP3={setup.tp3:.5f}"
                )

        return setups

    def _build_setup(
        self,
        symbol: str,
        direction: str,
        entry: dict,
        sweep: dict,
        mtf: MTFAnalysis,
    ) -> Optional[TradeSetup]:
        entry_price = entry["entry_price"]
        atr_val = entry["atr_value"]

        if atr_val == 0:
            return None

        # Stop loss: ATR-based or structure-based (whichever is tighter)
        atr_sl_dist = atr_val * self._atr_sl_mult

        if direction == "long":
            atr_stop = entry_price - atr_sl_dist
            structure_stop = self._get_structure_stop_long(mtf)
            sl = max(atr_stop, structure_stop) if structure_stop and self._use_structure_sl else atr_stop
            sl = min(sl, entry_price - atr_val * 0.5)  # minimum distance

            risk = entry_price - sl
            tp1 = entry_price + risk * 1.0
            tp2 = entry_price + risk * 1.5
            tp3 = entry_price + risk * 2.0

        else:
            atr_stop = entry_price + atr_sl_dist
            structure_stop = self._get_structure_stop_short(mtf)
            sl = min(atr_stop, structure_stop) if structure_stop and self._use_structure_sl else atr_stop
            sl = max(sl, entry_price + atr_val * 0.5)

            risk = sl - entry_price
            tp1 = entry_price - risk * 1.0
            tp2 = entry_price - risk * 1.5
            tp3 = entry_price - risk * 2.0

        features = self._build_features(direction, entry, sweep, mtf)

        return TradeSetup(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            stop_loss=sl,
            tp1=tp1,
            tp2=tp2,
            tp3=tp3,
            atr_value=atr_val,
            confidence_features=features,
            notes=f"sweep@{sweep.get('sweep_level', 0):.5f} pullback_dist={entry['distance_atr']:.2f}ATR",
        )

    def _get_structure_stop_long(self, mtf: MTFAnalysis) -> float | None:
        if mtf.m5_structure and mtf.m5_structure.swing_points:
            lows = [sp for sp in mtf.m5_structure.swing_points if sp.type == "low"]
            if lows:
                return min(sp.price for sp in lows[-3:])
        return None

    def _get_structure_stop_short(self, mtf: MTFAnalysis) -> float | None:
        if mtf.m5_structure and mtf.m5_structure.swing_points:
            highs = [sp for sp in mtf.m5_structure.swing_points if sp.type == "high"]
            if highs:
                return max(sp.price for sp in highs[-3:])
        return None

    def _build_features(
        self, direction: str, entry: dict, sweep: dict, mtf: MTFAnalysis
    ) -> dict:
        """Build feature dict for the AI confidence scorer."""
        m15_bos_count = len(mtf.m15_structure.structure_breaks) if mtf.m15_structure else 0
        m5_bos_count = len(mtf.m5_structure.structure_breaks) if mtf.m5_structure else 0

        return {
            "direction": 1.0 if direction == "long" else 0.0,
            "h1_bias_aligned": 1.0,
            "m15_bos_count": float(m15_bos_count),
            "m5_bos_count": float(m5_bos_count),
            "pullback_distance_atr": entry["distance_atr"],
            "atr_value": entry["atr_value"],
            "rsi_m5": mtf.current_rsi_m5,
            "ema_distance": abs(entry["entry_price"] - mtf.ema_21_m5) / entry["atr_value"] if entry["atr_value"] else 0,
            "sweep_wick_size": abs(sweep.get("sweep_high", sweep.get("sweep_low", 0)) - sweep.get("sweep_level", 0)),
        }
