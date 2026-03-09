"""
Strategy Generator.

Produces 200+ unique trading strategies across seven families:
  1. Trend following (EMA/SMA crossovers)
  2. Breakout (Bollinger, channel, VWAP)
  3. Mean reversion (RSI, Bollinger bounce)
  4. Volatility expansion (ATR expansion)
  5. Liquidity sweep (swing-level sweep + rejection)
  6. Market structure break (BOS / CHoCH)
  7. Momentum (MACD, RSI momentum)

Each strategy defines entry/exit conditions, SL, TP, and position-sizing
rules as a StrategyConfig.
"""
from __future__ import annotations

import hashlib
import itertools
from typing import List

from app.discovery.indicators import bb_col
from app.discovery.strategy_config import Condition, StrategyConfig


def _tag(family: str, params: dict) -> str:
    raw = f"{family}_{'_'.join(str(v) for v in params.values())}"
    short_hash = hashlib.md5(raw.encode()).hexdigest()[:6]
    return f"{family}_{short_hash}"


# ── Family builders ──────────────────────────────────────────────


def _trend_ema_cross() -> List[StrategyConfig]:
    strats: List[StrategyConfig] = []
    fast_periods = [5, 8, 9, 10, 13]
    slow_periods = [21, 30, 50, 100]
    rsi_filters = [None, 70, 80]
    sl_mults = [1.5, 2.0]
    tp_rrs = [1.5, 2.0, 3.0]

    for fp, sp, rf, sl, tp in itertools.product(
        fast_periods, slow_periods, rsi_filters, sl_mults, tp_rrs
    ):
        if fp >= sp:
            continue
        p = dict(fast=fp, slow=sp, rsi_filter=rf, sl=sl, tp=tp)
        le = [Condition(f"ema_{fp}", "cross_above", f"ema_{sp}")]
        se = [Condition(f"ema_{fp}", "cross_below", f"ema_{sp}")]
        if rf is not None:
            le.append(Condition(f"rsi_14", "<", rf))
            se.append(Condition(f"rsi_14", ">", 100 - rf))
        lx = [Condition(f"ema_{fp}", "cross_below", f"ema_{sp}")]
        sx = [Condition(f"ema_{fp}", "cross_above", f"ema_{sp}")]
        strats.append(StrategyConfig(
            name=_tag("trend_ema", p), family="trend_following",
            params=p, long_entry=le, short_entry=se,
            long_exit=lx, short_exit=sx,
            sl_atr_mult=sl, tp_rr=tp,
            description=f"EMA {fp}/{sp} cross"
            + (f" RSI<{rf}" if rf else ""),
        ))
    return strats


def _trend_sma_cross() -> List[StrategyConfig]:
    strats: List[StrategyConfig] = []
    fast_periods = [10, 20, 50]
    slow_periods = [50, 100, 200]
    macd_filters = [False, True]
    sl_mults = [1.5, 2.0]
    tp_rrs = [1.5, 2.0]

    for fp, sp, mf, sl, tp in itertools.product(
        fast_periods, slow_periods, macd_filters, sl_mults, tp_rrs
    ):
        if fp >= sp:
            continue
        p = dict(fast=fp, slow=sp, macd_filter=mf, sl=sl, tp=tp)
        le = [Condition(f"sma_{fp}", "cross_above", f"sma_{sp}")]
        se = [Condition(f"sma_{fp}", "cross_below", f"sma_{sp}")]
        if mf:
            le.append(Condition("macd_hist_12_26_9", ">", 0))
            se.append(Condition("macd_hist_12_26_9", "<", 0))
        strats.append(StrategyConfig(
            name=_tag("trend_sma", p), family="trend_following",
            params=p, long_entry=le, short_entry=se,
            long_exit=[Condition(f"sma_{fp}", "cross_below", f"sma_{sp}")],
            short_exit=[Condition(f"sma_{fp}", "cross_above", f"sma_{sp}")],
            sl_atr_mult=sl, tp_rr=tp,
            description=f"SMA {fp}/{sp}" + (" +MACD" if mf else ""),
        ))
    return strats


def _breakout_bollinger() -> List[StrategyConfig]:
    strats: List[StrategyConfig] = []
    bb_periods = [14, 20, 30]
    bb_stds = [1.5, 2.0, 2.5]
    confirms = ["none", "momentum", "rsi"]
    sl_mults = [1.5, 2.0]
    tp_rrs = [1.5, 2.0, 3.0]

    for period, std, conf, sl, tp in itertools.product(
        bb_periods, bb_stds, confirms, sl_mults, tp_rrs
    ):
        upper = bb_col("upper", period, std)
        lower = bb_col("lower", period, std)
        p = dict(period=period, std=std, confirm=conf, sl=sl, tp=tp)

        le = [Condition("close", ">", upper)]
        se = [Condition("close", "<", lower)]
        if conf == "momentum":
            le.append(Condition("momentum_10", ">", 0))
            se.append(Condition("momentum_10", "<", 0))
        elif conf == "rsi":
            le.append(Condition("rsi_14", ">", 50))
            se.append(Condition("rsi_14", "<", 50))

        mid = bb_col("mid", period, std)
        strats.append(StrategyConfig(
            name=_tag("brk_bb", p), family="breakout",
            params=p, long_entry=le, short_entry=se,
            long_exit=[Condition("close", "<", mid)],
            short_exit=[Condition("close", ">", mid)],
            sl_atr_mult=sl, tp_rr=tp,
            description=f"BB({period},{std}) breakout"
            + (f" +{conf}" if conf != "none" else ""),
        ))
    return strats


def _breakout_channel() -> List[StrategyConfig]:
    strats: List[StrategyConfig] = []
    periods = [10, 14, 20, 30]
    sl_mults = [1.5, 2.0]
    tp_rrs = [1.5, 2.0, 3.0]

    for period, sl, tp in itertools.product(periods, sl_mults, tp_rrs):
        p = dict(period=period, sl=sl, tp=tp)
        strats.append(StrategyConfig(
            name=_tag("brk_ch", p), family="breakout",
            params=p,
            long_entry=[Condition("close", ">", f"highest_{period}")],
            short_entry=[Condition("close", "<", f"lowest_{period}")],
            long_exit=[Condition("close", "<", f"ema_{min(period, 21)}")],
            short_exit=[Condition("close", ">", f"ema_{min(period, 21)}")],
            sl_atr_mult=sl, tp_rr=tp,
            description=f"Channel breakout {period}-bar",
        ))
    return strats


def _breakout_vwap() -> List[StrategyConfig]:
    strats: List[StrategyConfig] = []
    confirms = ["none", "rsi", "ema"]
    sl_mults = [1.5, 2.0]
    tp_rrs = [1.5, 2.0]

    for conf, sl, tp in itertools.product(confirms, sl_mults, tp_rrs):
        p = dict(confirm=conf, sl=sl, tp=tp)
        le = [Condition("close", ">", "vwap")]
        se = [Condition("close", "<", "vwap")]
        if conf == "rsi":
            le.append(Condition("rsi_14", ">", 50))
            se.append(Condition("rsi_14", "<", 50))
        elif conf == "ema":
            le.append(Condition("ema_9", ">", "ema_21"))
            se.append(Condition("ema_9", "<", "ema_21"))
        strats.append(StrategyConfig(
            name=_tag("brk_vwap", p), family="breakout",
            params=p, long_entry=le, short_entry=se,
            long_exit=[Condition("close", "<", "vwap")],
            short_exit=[Condition("close", ">", "vwap")],
            sl_atr_mult=sl, tp_rr=tp,
            description=f"VWAP breakout" + (f" +{conf}" if conf != "none" else ""),
        ))
    return strats


def _mean_reversion_rsi() -> List[StrategyConfig]:
    strats: List[StrategyConfig] = []
    rsi_periods = [7, 9, 14, 21]
    os_levels = [20, 25, 30]
    ob_levels = [70, 75, 80]
    confirms = ["none", "bb_touch", "ema_slope"]
    sl_mults = [1.5, 2.0, 2.5]
    tp_rrs = [1.0, 1.5, 2.0]

    for rp, osl, obl, conf, sl, tp in itertools.product(
        rsi_periods, os_levels, ob_levels, confirms, sl_mults, tp_rrs
    ):
        if osl >= obl:
            continue
        p = dict(rsi_period=rp, oversold=osl, overbought=obl,
                 confirm=conf, sl=sl, tp=tp)

        le = [Condition(f"rsi_{rp}", "<", osl)]
        se = [Condition(f"rsi_{rp}", ">", obl)]
        if conf == "bb_touch":
            le.append(Condition("close", "<", bb_col("lower", 20, 2.0)))
            se.append(Condition("close", ">", bb_col("upper", 20, 2.0)))
        elif conf == "ema_slope":
            le.append(Condition("ema_50", ">", "ema_200"))
            se.append(Condition("ema_50", "<", "ema_200"))

        lx = [Condition(f"rsi_{rp}", ">", 50)]
        sx = [Condition(f"rsi_{rp}", "<", 50)]

        strats.append(StrategyConfig(
            name=_tag("mr_rsi", p), family="mean_reversion",
            params=p, long_entry=le, short_entry=se,
            long_exit=lx, short_exit=sx,
            sl_atr_mult=sl, tp_rr=tp,
            description=f"RSI({rp}) MR {osl}/{obl}"
            + (f" +{conf}" if conf != "none" else ""),
        ))
    return strats


def _mean_reversion_bb() -> List[StrategyConfig]:
    strats: List[StrategyConfig] = []
    bb_periods = [14, 20, 30]
    bb_stds = [1.5, 2.0, 2.5]
    rsi_confirms = [None, 30, 35]
    sl_mults = [1.5, 2.0]
    tp_types = ["mid", "opposite"]

    for period, std, rc, sl, tpt in itertools.product(
        bb_periods, bb_stds, rsi_confirms, sl_mults, tp_types
    ):
        p = dict(period=period, std=std, rsi_confirm=rc, sl=sl, tp_type=tpt)
        upper = bb_col("upper", period, std)
        lower = bb_col("lower", period, std)
        mid = bb_col("mid", period, std)

        le = [Condition("close", "<", lower)]
        se = [Condition("close", ">", upper)]
        if rc is not None:
            le.append(Condition("rsi_14", "<", rc))
            se.append(Condition("rsi_14", ">", 100 - rc))

        if tpt == "mid":
            lx = [Condition("close", ">", mid)]
            sx = [Condition("close", "<", mid)]
            tp_rr = 1.5
        else:
            lx = [Condition("close", ">", upper)]
            sx = [Condition("close", "<", lower)]
            tp_rr = 2.5

        strats.append(StrategyConfig(
            name=_tag("mr_bb", p), family="mean_reversion",
            params=p, long_entry=le, short_entry=se,
            long_exit=lx, short_exit=sx,
            sl_atr_mult=sl, tp_rr=tp_rr,
            description=f"BB({period},{std}) bounce"
            + (f" RSI<{rc}" if rc else ""),
        ))
    return strats


def _volatility_expansion() -> List[StrategyConfig]:
    strats: List[StrategyConfig] = []
    atr_periods = [10, 14, 20]
    expansion_mults = [1.2, 1.5, 2.0]
    directions = ["ema_slope", "macd", "rsi"]
    sl_mults = [1.5, 2.0]
    tp_rrs = [1.5, 2.0, 3.0]

    for ap, em, d, sl, tp in itertools.product(
        atr_periods, expansion_mults, directions, sl_mults, tp_rrs
    ):
        p = dict(atr_period=ap, expansion=em, direction=d, sl=sl, tp=tp)
        atr_col = f"atr_{ap}"
        sma_atr = f"sma_atr_{ap}"

        le: list = [
            Condition(atr_col, ">", f"__atr_sma_{ap}_x_{int(em * 10)}"),
        ]
        se: list = [
            Condition(atr_col, ">", f"__atr_sma_{ap}_x_{int(em * 10)}"),
        ]
        if d == "ema_slope":
            le.append(Condition("ema_9", ">", "ema_21"))
            se.append(Condition("ema_9", "<", "ema_21"))
        elif d == "macd":
            le.append(Condition("macd_hist_12_26_9", ">", 0))
            se.append(Condition("macd_hist_12_26_9", "<", 0))
        elif d == "rsi":
            le.append(Condition("rsi_14", ">", 55))
            se.append(Condition("rsi_14", "<", 45))

        strats.append(StrategyConfig(
            name=_tag("vol_exp", p), family="volatility_expansion",
            params=p, long_entry=le, short_entry=se,
            sl_atr_mult=sl, tp_rr=tp,
            description=f"ATR({ap}) expansion x{em} dir={d}",
        ))
    return strats


def _liquidity_sweep() -> List[StrategyConfig]:
    strats: List[StrategyConfig] = []
    swing_lookbacks = [5, 10, 14]
    confirms = ["close_rejection", "rsi", "ema"]
    sl_mults = [1.0, 1.5, 2.0]
    tp_rrs = [1.5, 2.0, 3.0]

    for slb, conf, sl, tp in itertools.product(
        swing_lookbacks, confirms, sl_mults, tp_rrs
    ):
        p = dict(swing_lb=slb, confirm=conf, sl=sl, tp=tp)
        low_col = f"lowest_{slb}"
        high_col = f"highest_{slb}"

        le = [
            Condition("low", "<", f"__prev_{low_col}"),
            Condition("close", ">", "open"),
        ]
        se = [
            Condition("high", ">", f"__prev_{high_col}"),
            Condition("close", "<", "open"),
        ]
        if conf == "rsi":
            le.append(Condition("rsi_14", "<", 40))
            se.append(Condition("rsi_14", ">", 60))
        elif conf == "ema":
            le.append(Condition("close", ">", "ema_21"))
            se.append(Condition("close", "<", "ema_21"))

        strats.append(StrategyConfig(
            name=_tag("liq_sweep", p), family="liquidity_sweep",
            params=p, long_entry=le, short_entry=se,
            sl_atr_mult=sl, tp_rr=tp,
            description=f"Sweep {slb}-bar lows/highs +{conf}",
        ))
    return strats


def _market_structure_break() -> List[StrategyConfig]:
    strats: List[StrategyConfig] = []
    swing_lookbacks = [5, 10, 14]
    entry_types = ["immediate", "pullback_ema"]
    sl_mults = [1.5, 2.0]
    tp_rrs = [1.5, 2.0, 3.0]

    for slb, et, sl, tp in itertools.product(
        swing_lookbacks, entry_types, sl_mults, tp_rrs
    ):
        p = dict(swing_lb=slb, entry=et, sl=sl, tp=tp)
        high_col = f"highest_{slb}"
        low_col = f"lowest_{slb}"

        le = [Condition("close", ">", f"__prev_{high_col}")]
        se = [Condition("close", "<", f"__prev_{low_col}")]

        if et == "pullback_ema":
            le.append(Condition("close", ">", "ema_9"))
            se.append(Condition("close", "<", "ema_9"))

        strats.append(StrategyConfig(
            name=_tag("msb", p), family="market_structure_break",
            params=p, long_entry=le, short_entry=se,
            sl_atr_mult=sl, tp_rr=tp,
            description=f"MSB {slb}-bar"
            + (" +pullback" if et == "pullback_ema" else ""),
        ))
    return strats


def _momentum() -> List[StrategyConfig]:
    strats: List[StrategyConfig] = []

    # MACD cross strategies
    for fast, slow, sig in [(8, 21, 5), (12, 26, 9), (5, 13, 4)]:
        for conf in ["none", "ema_trend", "rsi"]:
            for sl in [1.5, 2.0]:
                for tp in [1.5, 2.0, 3.0]:
                    tag = f"{fast}_{slow}_{sig}"
                    p = dict(fast=fast, slow=slow, sig=sig,
                             confirm=conf, sl=sl, tp=tp)
                    le = [Condition(f"macd_{tag}", "cross_above",
                                    f"macd_signal_{tag}")]
                    se = [Condition(f"macd_{tag}", "cross_below",
                                    f"macd_signal_{tag}")]
                    if conf == "ema_trend":
                        le.append(Condition("ema_20", ">", "ema_50"))
                        se.append(Condition("ema_20", "<", "ema_50"))
                    elif conf == "rsi":
                        le.append(Condition("rsi_14", ">", 45))
                        le.append(Condition("rsi_14", "<", 75))
                        se.append(Condition("rsi_14", "<", 55))
                        se.append(Condition("rsi_14", ">", 25))

                    strats.append(StrategyConfig(
                        name=_tag("mom_macd", p), family="momentum",
                        params=p, long_entry=le, short_entry=se,
                        long_exit=[Condition(f"macd_{tag}", "cross_below",
                                             f"macd_signal_{tag}")],
                        short_exit=[Condition(f"macd_{tag}", "cross_above",
                                              f"macd_signal_{tag}")],
                        sl_atr_mult=sl, tp_rr=tp,
                        description=f"MACD({fast},{slow},{sig})"
                        + (f" +{conf}" if conf != "none" else ""),
                    ))

    # RSI momentum strategies
    for rp in [9, 14]:
        for thresh in [55, 60]:
            for sl in [1.5, 2.0]:
                for tp in [1.5, 2.0]:
                    p = dict(rsi_period=rp, threshold=thresh, sl=sl, tp=tp)
                    strats.append(StrategyConfig(
                        name=_tag("mom_rsi", p), family="momentum",
                        params=p,
                        long_entry=[
                            Condition(f"rsi_{rp}", "cross_above", thresh),
                            Condition("ema_9", ">", "ema_21"),
                        ],
                        short_entry=[
                            Condition(f"rsi_{rp}", "cross_below", 100 - thresh),
                            Condition("ema_9", "<", "ema_21"),
                        ],
                        long_exit=[Condition(f"rsi_{rp}", ">", 75)],
                        short_exit=[Condition(f"rsi_{rp}", "<", 25)],
                        sl_atr_mult=sl, tp_rr=tp,
                        description=f"RSI({rp}) momentum cross {thresh}",
                    ))
    return strats


# ── Public API ───────────────────────────────────────────────


def generate_strategies(target: int = 200, seed: int = 42) -> List[StrategyConfig]:
    """
    Generate at least *target* diverse trading strategies.

    Strategies are drawn from seven families.  If a family produces more
    candidates than its quota, a deterministic sample is taken to cap the
    total while maintaining diversity.
    """
    import random
    rng = random.Random(seed)

    families = [
        ("trend_ema", _trend_ema_cross, 35),
        ("trend_sma", _trend_sma_cross, 16),
        ("brk_bb", _breakout_bollinger, 24),
        ("brk_ch", _breakout_channel, 16),
        ("brk_vwap", _breakout_vwap, 10),
        ("mr_rsi", _mean_reversion_rsi, 28),
        ("mr_bb", _mean_reversion_bb, 22),
        ("vol_exp", _volatility_expansion, 22),
        ("liq_sweep", _liquidity_sweep, 22),
        ("msb", _market_structure_break, 16),
        ("momentum", _momentum, 24),
    ]

    all_strats: List[StrategyConfig] = []

    for _, builder, quota in families:
        candidates = builder()
        if len(candidates) > quota:
            candidates = rng.sample(candidates, quota)
        all_strats.extend(candidates)

    seen_names: set = set()
    unique: List[StrategyConfig] = []
    for s in all_strats:
        if s.name not in seen_names:
            seen_names.add(s.name)
            unique.append(s)

    if len(unique) < target:
        extra_needed = target - len(unique)
        extras = _trend_ema_cross() + _breakout_bollinger() + _mean_reversion_rsi()
        rng.shuffle(extras)
        for s in extras:
            if s.name not in seen_names:
                seen_names.add(s.name)
                unique.append(s)
                if len(unique) >= target:
                    break

    return unique
