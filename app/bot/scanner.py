"""
Market Scanner.

Scans multiple symbols and timeframes for valid trade setups.
Runs on a configurable interval (default: 60 seconds).
"""
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
import pandas as pd

from app.brokers.base import BaseBroker, OHLCV
from app.core.strategy.multi_timeframe import MultiTimeframeAnalyzer, MTFAnalysis
from app.core.ai.classifier import TradeClassifier, PredictionResult
from app.core.session_filter import SessionFilter
from app.core.news_filter import NewsFilter
from app.core.risk_manager import RiskManager
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("scanner")

UTC = timezone.utc


class ScanResult:
    """Result of scanning a single symbol."""

    def __init__(
        self,
        symbol: str,
        market_type: str,
        mtf: MTFAnalysis,
        prediction: PredictionResult,
        session: str,
        news_clear: bool,
        risk_ok: bool,
        timestamp: datetime = None,
    ):
        self.symbol = symbol
        self.market_type = market_type
        self.mtf = mtf
        self.prediction = prediction
        self.session = session
        self.news_clear = news_clear
        self.risk_ok = risk_ok
        self.timestamp = timestamp or datetime.now(UTC)

    @property
    def is_valid(self) -> bool:
        return (
            self.mtf.tradeable
            and self.prediction.should_trade
            and self.news_clear
            and self.risk_ok
        )

    def __repr__(self):
        return (
            f"<ScanResult {self.symbol} tradeable={self.mtf.tradeable} "
            f"conf={self.prediction.confidence:.2f} valid={self.is_valid}>"
        )


class MarketScanner:
    """
    Scans all configured symbols for trade setups.

    Workflow per symbol:
    1. Fetch H1, M15, M5 OHLCV data
    2. Run MTF analysis (sweep + BOS + pullback)
    3. Score with AI classifier
    4. Check session filter
    5. Check news filter
    6. Check risk limits
    7. Return valid setups for execution
    """

    def __init__(
        self,
        forex_broker: BaseBroker,
        crypto_broker: BaseBroker,
        mtf_analyzer: MultiTimeframeAnalyzer,
        classifier: TradeClassifier,
        session_filter: SessionFilter,
        news_filter: NewsFilter,
        risk_manager: RiskManager,
        forex_symbols: List[str] = None,
        crypto_symbols: List[str] = None,
    ):
        self.forex_broker = forex_broker
        self.crypto_broker = crypto_broker
        self.mtf_analyzer = mtf_analyzer
        self.classifier = classifier
        self.session_filter = session_filter
        self.news_filter = news_filter
        self.risk_manager = risk_manager

        self.forex_symbols = forex_symbols or settings.forex_symbol_list
        self.crypto_symbols = crypto_symbols or settings.crypto_symbol_list

        self._scan_count = 0
        self._last_scan: Optional[datetime] = None

    async def scan_all(self) -> List[ScanResult]:
        """
        Scan all symbols and return valid trade setups.
        """
        self._scan_count += 1
        self._last_scan = datetime.now(UTC)

        # Check session first (skip crypto during off-hours only if configured)
        session_info = self.session_filter.get_current_session()
        session_name = session_info.session_type

        logger.info(
            f"Scan #{self._scan_count} | Session: {session_info.name} "
            f"({'active' if session_info.is_active else 'inactive'})"
        )

        # Refresh news if needed
        if self.news_filter.needs_refresh():
            await self.news_filter.refresh_events()

        valid_results: List[ScanResult] = []

        # Check global risk limits
        risk_status = self.risk_manager.check_risk_limits()
        if not risk_status.can_trade:
            logger.warning(f"Global risk limit hit: {risk_status.reason}")
            return valid_results

        # Scan forex (only during active sessions)
        if session_info.is_active:
            forex_tasks = [
                self._scan_symbol(symbol, "forex", self.forex_broker, session_name)
                for symbol in self.forex_symbols
            ]
            forex_results = await asyncio.gather(*forex_tasks, return_exceptions=True)
            for r in forex_results:
                if isinstance(r, ScanResult) and r.is_valid:
                    valid_results.append(r)
                    logger.info(f"Valid forex setup: {r}")

        # Scan crypto (24/7 but with session preference)
        crypto_tasks = [
            self._scan_symbol(symbol, "crypto", self.crypto_broker, session_name)
            for symbol in self.crypto_symbols
        ]
        crypto_results = await asyncio.gather(*crypto_tasks, return_exceptions=True)
        for r in crypto_results:
            if isinstance(r, ScanResult) and r.is_valid:
                valid_results.append(r)
                logger.info(f"Valid crypto setup: {r}")

        logger.info(
            f"Scan #{self._scan_count} complete: {len(valid_results)} valid setups found"
        )

        # Sort by confidence (highest first)
        valid_results.sort(key=lambda x: x.prediction.confidence, reverse=True)

        return valid_results

    async def _scan_symbol(
        self,
        symbol: str,
        market_type: str,
        broker: BaseBroker,
        session_name: str,
    ) -> Optional[ScanResult]:
        """Scan a single symbol for trade setups."""
        try:
            # Fetch OHLCV data for all 3 timeframes concurrently
            h1_task = broker.get_ohlcv(symbol, settings.H1_TIMEFRAME, settings.LOOKBACK_CANDLES)
            m15_task = broker.get_ohlcv(symbol, settings.M15_TIMEFRAME, settings.LOOKBACK_CANDLES)
            m5_task = broker.get_ohlcv(symbol, settings.M5_TIMEFRAME, settings.LOOKBACK_CANDLES)

            h1_ohlcv, m15_ohlcv, m5_ohlcv = await asyncio.gather(h1_task, m15_task, m5_task)

            if any(x is None for x in [h1_ohlcv, m15_ohlcv, m5_ohlcv]):
                logger.debug(f"{symbol}: failed to fetch OHLCV data")
                return None

            h1_df = h1_ohlcv.data
            m15_df = m15_ohlcv.data
            m5_df = m5_ohlcv.data

            if len(h1_df) < 50 or len(m15_df) < 30 or len(m5_df) < 20:
                logger.debug(f"{symbol}: insufficient data")
                return None

            # MTF analysis
            mtf = self.mtf_analyzer.analyze(symbol, h1_df, m15_df, m5_df)

            # AI confidence scoring
            prediction = self.classifier.predict(h1_df, m15_df, m5_df, mtf, session_name)

            # News filter
            news_clear = self.news_filter.is_news_clear(symbol)

            # Individual risk check (session trades)
            risk_status = self.risk_manager.check_risk_limits()
            risk_ok = risk_status.can_trade

            result = ScanResult(
                symbol=symbol,
                market_type=market_type,
                mtf=mtf,
                prediction=prediction,
                session=session_name,
                news_clear=news_clear,
                risk_ok=risk_ok,
            )

            if mtf.tradeable:
                logger.debug(
                    f"{symbol}: tradeable=True conf={prediction.confidence:.2f} "
                    f"quality={mtf.setup_quality} news_clear={news_clear}"
                )

            return result

        except Exception as e:
            logger.error(f"Scanner error for {symbol}: {e}", exc_info=True)
            return None

    @property
    def scan_stats(self) -> dict:
        return {
            "total_scans": self._scan_count,
            "last_scan": self._last_scan.isoformat() if self._last_scan else None,
            "forex_symbols": len(self.forex_symbols),
            "crypto_symbols": len(self.crypto_symbols),
        }
