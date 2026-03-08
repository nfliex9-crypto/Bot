from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd
from loguru import logger

from app.analysis.indicators import atr, ema, rsi
from app.analysis.market_structure import Bias, StructureResult, analyse_structure
from app.market_data.base import MarketDataProvider


@dataclass
class MTFAnalysis:
    symbol: str
    h1_bias: Bias = Bias.NEUTRAL
    m15_structure: Optional[StructureResult] = None
    m5_structure: Optional[StructureResult] = None
    h1_df: Optional[pd.DataFrame] = None
    m15_df: Optional[pd.DataFrame] = None
    m5_df: Optional[pd.DataFrame] = None
    current_atr_m5: float = 0.0
    current_rsi_m5: float = 50.0
    ema_21_m5: float = 0.0
    ema_50_m15: float = 0.0
    is_valid: bool = False


class MultiTimeframeAnalyzer:
    """
    Multi-timeframe engine:
      - H1  → market bias (trend direction)
      - M15 → trend structure (BOS/CHoCH)
      - M5  → execution timing
    """

    def __init__(self, provider: MarketDataProvider) -> None:
        self._provider = provider

    async def analyse(self, symbol: str) -> MTFAnalysis:
        result = MTFAnalysis(symbol=symbol)

        try:
            h1_df = await self._provider.get_candles(symbol, "H1", count=200)
            m15_df = await self._provider.get_candles(symbol, "M15", count=200)
            m5_df = await self._provider.get_candles(symbol, "M5", count=200)
        except Exception as exc:
            logger.error(f"MTF data fetch failed for {symbol}: {exc}")
            return result

        if h1_df.empty or m15_df.empty or m5_df.empty:
            logger.warning(f"Incomplete MTF data for {symbol}")
            return result

        result.h1_df = h1_df
        result.m15_df = m15_df
        result.m5_df = m5_df

        # H1 bias
        h1_struct = analyse_structure(h1_df, lookback=5)
        result.h1_bias = h1_struct.bias

        # M15 structure
        result.m15_structure = analyse_structure(m15_df, lookback=5)
        result.ema_50_m15 = float(ema(m15_df["close"], 50).iloc[-1])

        # M5 execution data
        result.m5_structure = analyse_structure(m5_df, lookback=3)
        result.current_atr_m5 = float(atr(m5_df, 14).iloc[-1])
        result.current_rsi_m5 = float(rsi(m5_df["close"], 14).iloc[-1])
        result.ema_21_m5 = float(ema(m5_df["close"], 21).iloc[-1])

        result.is_valid = True
        logger.debug(
            f"MTF analysis {symbol}: H1={result.h1_bias.value} "
            f"ATR={result.current_atr_m5:.5f} RSI={result.current_rsi_m5:.1f}"
        )
        return result
