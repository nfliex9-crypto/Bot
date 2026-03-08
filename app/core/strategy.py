"""Strategy logic: Liquidity Sweep, Break of Structure, Pullback Entry."""
import pandas as pd
from .models import TradeSignal, TradeDirection, StrategyType, StopType, MarketStructure, MarketType
from .multi_timeframe import build_market_structure, get_m5_execution_context
from .indicators import atr, detect_liquidity_zones, structure_stop_level
from datetime import datetime


def liquidity_sweep_signal(
    ohlcv_h1: pd.DataFrame,
    ohlcv_m15: pd.DataFrame,
    ohlcv_m5: pd.DataFrame,
    symbol: str,
    market_type: MarketType,
    atr_multiplier: float = 2.0,
) -> TradeSignal | None:
    """
    Liquidity Sweep: Price sweeps liquidity (equal highs/lows) then reverses.
    Entry on pullback after sweep.
    """
    if len(ohlcv_m5) < 20 or len(ohlcv_m15) < 20 or len(ohlcv_h1) < 20:
        return None

    high_zones, low_zones = detect_liquidity_zones(ohlcv_m15)
    structure_h1 = build_market_structure(ohlcv_h1, "H1")
    structure_m15 = build_market_structure(ohlcv_m15, "M15")
    ctx = get_m5_execution_context(ohlcv_m5)

    if not ctx["ready"]:
        return None

    atr_val = atr(ohlcv_m5, 14).iloc[-1]
    if pd.isna(atr_val) or atr_val <= 0:
        return None

    close = ctx["last_close"]
    last_high = ctx["last_high"]
    last_low = ctx["last_low"]

    # Bullish sweep: price swept below recent lows then closed above
    for zone in low_zones:
        if last_low < zone * 0.999 and close > zone and structure_h1.bias == "bullish":
            sl = structure_stop_level(
                [s.price for s in structure_m15.lower_highs],
                [s.price for s in structure_m15.higher_lows],
                "long",
            )
            if sl <= 0:
                sl = last_low - atr_val * atr_multiplier
            entry = close
            risk = entry - sl
            return TradeSignal(
                symbol=symbol,
                direction=TradeDirection.LONG,
                strategy=StrategyType.LIQUIDITY_SWEEP,
                entry_price=entry,
                stop_loss=sl,
                tp1=entry + risk,
                tp2=entry + risk * 1.5,
                tp3=entry + risk * 2,
                stop_type=StopType.STRUCTURE,
                atr_value=atr_val,
                risk_reward=2.0,
                confidence=0.0,  # AI fills this
                market_type=market_type,
                timestamp=datetime.utcnow(),
                market_structure=structure_m15,
            )

    # Bearish sweep
    for zone in high_zones:
        if last_high > zone * 1.001 and close < zone and structure_h1.bias == "bearish":
            sl = structure_stop_level(
                [s.price for s in structure_m15.lower_highs],
                [s.price for s in structure_m15.higher_lows],
                "short",
            )
            if sl <= 0:
                sl = last_high + atr_val * atr_multiplier
            entry = close
            risk = sl - entry
            return TradeSignal(
                symbol=symbol,
                direction=TradeDirection.SHORT,
                strategy=StrategyType.LIQUIDITY_SWEEP,
                entry_price=entry,
                stop_loss=sl,
                tp1=entry - risk,
                tp2=entry - risk * 1.5,
                tp3=entry - risk * 2,
                stop_type=StopType.STRUCTURE,
                atr_value=atr_val,
                risk_reward=2.0,
                confidence=0.0,
                market_type=market_type,
                timestamp=datetime.utcnow(),
                market_structure=structure_m15,
            )
    return None


def break_of_structure_signal(
    ohlcv_h1: pd.DataFrame,
    ohlcv_m15: pd.DataFrame,
    ohlcv_m5: pd.DataFrame,
    symbol: str,
    market_type: MarketType,
    atr_multiplier: float = 2.0,
) -> TradeSignal | None:
    """
    Break of Structure: Price breaks recent swing high/low in trend direction.
    """
    if len(ohlcv_m5) < 20 or len(ohlcv_m15) < 20 or len(ohlcv_h1) < 20:
        return None

    structure_h1 = build_market_structure(ohlcv_h1, "H1")
    structure_m15 = build_market_structure(ohlcv_m15, "M15")
    ctx = get_m5_execution_context(ohlcv_m5)

    if not ctx["ready"]:
        return None

    atr_val = atr(ohlcv_m5, 14).iloc[-1]
    if pd.isna(atr_val) or atr_val <= 0:
        return None

    close = ctx["last_close"]
    last_high = ctx["last_high"]
    last_low = ctx["last_low"]

    # Bullish BOS
    if structure_h1.bias == "bullish" and structure_m15.higher_highs:
        recent_hh = max(s.price for s in structure_m15.higher_highs[-3:])
        if last_high > recent_hh and close > recent_hh:
            recent_hl = min(s.price for s in structure_m15.higher_lows[-3:]) if structure_m15.higher_lows else last_low - atr_val
            sl = recent_hl * 0.999
            entry = close
            risk = entry - sl
            return TradeSignal(
                symbol=symbol,
                direction=TradeDirection.LONG,
                strategy=StrategyType.BREAK_OF_STRUCTURE,
                entry_price=entry,
                stop_loss=sl,
                tp1=entry + risk,
                tp2=entry + risk * 1.5,
                tp3=entry + risk * 2,
                stop_type=StopType.STRUCTURE,
                atr_value=atr_val,
                risk_reward=2.0,
                confidence=0.0,
                market_type=market_type,
                timestamp=datetime.utcnow(),
                market_structure=structure_m15,
            )

    # Bearish BOS
    if structure_h1.bias == "bearish" and structure_m15.lower_lows:
        recent_ll = min(s.price for s in structure_m15.lower_lows[-3:])
        if last_low < recent_ll and close < recent_ll:
            recent_lh = max(s.price for s in structure_m15.lower_highs[-3:]) if structure_m15.lower_highs else last_high + atr_val
            sl = recent_lh * 1.001
            entry = close
            risk = sl - entry
            return TradeSignal(
                symbol=symbol,
                direction=TradeDirection.SHORT,
                strategy=StrategyType.BREAK_OF_STRUCTURE,
                entry_price=entry,
                stop_loss=sl,
                tp1=entry - risk,
                tp2=entry - risk * 1.5,
                tp3=entry - risk * 2,
                stop_type=StopType.STRUCTURE,
                atr_value=atr_val,
                risk_reward=2.0,
                confidence=0.0,
                market_type=market_type,
                timestamp=datetime.utcnow(),
                market_structure=structure_m15,
            )
    return None


def pullback_entry_signal(
    ohlcv_h1: pd.DataFrame,
    ohlcv_m15: pd.DataFrame,
    ohlcv_m5: pd.DataFrame,
    symbol: str,
    market_type: MarketType,
    atr_multiplier: float = 2.0,
) -> TradeSignal | None:
    """
    Pullback Entry: Enter on pullback to structure (HH/HL or LH/LL) in trend.
    """
    if len(ohlcv_m5) < 20 or len(ohlcv_m15) < 20 or len(ohlcv_h1) < 20:
        return None

    structure_h1 = build_market_structure(ohlcv_h1, "H1")
    structure_m15 = build_market_structure(ohlcv_m15, "M15")
    ctx = get_m5_execution_context(ohlcv_m5)

    if not ctx["ready"]:
        return None

    atr_val = atr(ohlcv_m5, 14).iloc[-1]
    if pd.isna(atr_val) or atr_val <= 0:
        return None

    close = ctx["last_close"]
    last_low = ctx["last_low"]
    last_high = ctx["last_high"]

    # Bullish pullback to HL
    if structure_h1.bias == "bullish" and structure_m15.higher_lows:
        support = structure_m15.higher_lows[-1].price
        buffer = atr_val * 0.3
        if support - buffer <= last_low <= support + buffer and close > support:
            sl = support - atr_val * atr_multiplier
            entry = close
            risk = entry - sl
            return TradeSignal(
                symbol=symbol,
                direction=TradeDirection.LONG,
                strategy=StrategyType.PULLBACK_ENTRY,
                entry_price=entry,
                stop_loss=sl,
                tp1=entry + risk,
                tp2=entry + risk * 1.5,
                tp3=entry + risk * 2,
                stop_type=StopType.ATR,
                atr_value=atr_val,
                risk_reward=2.0,
                confidence=0.0,
                market_type=market_type,
                timestamp=datetime.utcnow(),
                market_structure=structure_m15,
            )

    # Bearish pullback to LH
    if structure_h1.bias == "bearish" and structure_m15.lower_highs:
        resistance = structure_m15.lower_highs[-1].price
        buffer = atr_val * 0.3
        if resistance - buffer <= last_high <= resistance + buffer and close < resistance:
            sl = resistance + atr_val * atr_multiplier
            entry = close
            risk = sl - entry
            return TradeSignal(
                symbol=symbol,
                direction=TradeDirection.SHORT,
                strategy=StrategyType.PULLBACK_ENTRY,
                entry_price=entry,
                stop_loss=sl,
                tp1=entry - risk,
                tp2=entry - risk * 1.5,
                tp3=entry - risk * 2,
                stop_type=StopType.ATR,
                atr_value=atr_val,
                risk_reward=2.0,
                confidence=0.0,
                market_type=market_type,
                timestamp=datetime.utcnow(),
                market_structure=structure_m15,
            )
    return None


def run_all_strategies(
    ohlcv_h1: pd.DataFrame,
    ohlcv_m15: pd.DataFrame,
    ohlcv_m5: pd.DataFrame,
    symbol: str,
    market_type: MarketType,
) -> list[TradeSignal]:
    """Run all strategies and return non-None signals."""
    signals = []
    for fn in [liquidity_sweep_signal, break_of_structure_signal, pullback_entry_signal]:
        sig = fn(ohlcv_h1, ohlcv_m15, ohlcv_m5, symbol, market_type)
        if sig:
            signals.append(sig)
    return signals
