from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from ai.model import TradingAIModel
from ai.scorer import ConfidenceScorer
from config.settings import Settings, TradingMode, settings
from core.enums import Market
from core.events import event_bus
from core.models import TradeSignal
from data.candle_manager import CandleManager
from data.feed import BinanceDataFeed, DataFeed, MT5DataFeed, PaperDataFeed
from database.connection import close_db, init_db
from database.repository import TradeRepository
from execution.base import BaseExecutor
from execution.binance_executor import BinanceExecutor
from execution.mt5_executor import MT5Executor
from execution.paper_executor import PaperExecutor
from execution.trade_manager import TradeManager
from filters.news_filter import NewsFilter
from filters.session_filter import SessionFilter
from risk.manager import RiskManager
from strategy.mtf_analyzer import MTFAnalyzer

logger = logging.getLogger(__name__)


class TradingEngine:
    """
    Core 24/7 trading engine.

    Cycle every ~60s:
      1. Check session & news filters
      2. Refresh candle data
      3. Run MTF analysis per symbol
      4. Score signals with AI
      5. Validate risk
      6. Execute accepted trades
      7. Monitor open trades (TP/SL/BE)
      8. Periodic AI retrain & account snapshots
    """

    def __init__(self) -> None:
        self._running = False
        self._repo = TradeRepository()
        self._session_filter = SessionFilter()
        self._news_filter = NewsFilter()
        self._ai_model = TradingAIModel()
        self._scorer = ConfidenceScorer(self._ai_model)
        self._risk: Optional[RiskManager] = None

        self._forex_feed: Optional[DataFeed] = None
        self._crypto_feed: Optional[DataFeed] = None
        self._forex_cm: Optional[CandleManager] = None
        self._crypto_cm: Optional[CandleManager] = None
        self._forex_analyzer: Optional[MTFAnalyzer] = None
        self._crypto_analyzer: Optional[MTFAnalyzer] = None

        self._forex_executor: Optional[BaseExecutor] = None
        self._crypto_executor: Optional[BaseExecutor] = None
        self._forex_tm: Optional[TradeManager] = None
        self._crypto_tm: Optional[TradeManager] = None

        self._last_retrain: Optional[datetime] = None
        self._last_snapshot: Optional[datetime] = None
        self._cycle_count = 0

    async def start(self) -> None:
        logger.info("=" * 60)
        logger.info("AI Trading Bot — Starting")
        logger.info("Mode: %s", settings.trading_mode.value.upper())
        logger.info("Balance: $%.2f | Risk: %.2f%% | Max DD: %.1f%%",
                     settings.account_balance, settings.risk_per_trade, settings.max_drawdown_pct)
        logger.info("=" * 60)

        await init_db()

        self._risk = RiskManager(self._repo)
        await self._init_feeds()
        await self._init_executors()
        await self._init_trade_managers()

        if self._forex_tm:
            await self._forex_tm.load_open_trades()
        if self._crypto_tm:
            await self._crypto_tm.load_open_trades()

        self._running = True
        logger.info("Engine started — entering main loop")

        try:
            await self._main_loop()
        except asyncio.CancelledError:
            logger.info("Engine shutting down (cancelled)")
        except Exception:
            logger.exception("Engine fatal error")
        finally:
            await self._shutdown()

    async def stop(self) -> None:
        self._running = False

    async def _main_loop(self) -> None:
        while self._running:
            try:
                self._cycle_count += 1
                await self._cycle()
            except Exception:
                logger.exception("Error in trading cycle %d", self._cycle_count)
            await asyncio.sleep(60)

    async def _cycle(self) -> None:
        now = datetime.utcnow()

        if self._forex_tm:
            await self._forex_tm.monitor_trades()
        if self._crypto_tm:
            await self._crypto_tm.monitor_trades()

        can_trade, reason = await self._risk.can_trade()
        if not can_trade:
            if self._cycle_count % 30 == 0:
                logger.info("Cannot trade: %s", reason)
            await self._periodic_tasks(now)
            return

        session_ok, session_msg = self._session_filter.should_trade(now)
        if not session_ok:
            if self._cycle_count % 60 == 0:
                logger.debug("Session: %s", session_msg)
            await self._periodic_tasks(now)
            return

        await self._news_filter.refresh()

        if self._forex_analyzer:
            for symbol in settings.forex_symbols:
                await self._analyze_and_trade(symbol, Market.FOREX)

        if self._crypto_analyzer:
            for symbol in settings.crypto_symbols:
                await self._analyze_and_trade(symbol, Market.CRYPTO)

        await self._periodic_tasks(now)

    async def _analyze_and_trade(self, symbol: str, market: Market) -> None:
        is_blackout, news_msg = self._news_filter.is_blackout(symbol)
        if is_blackout:
            logger.debug("News blackout for %s: %s", symbol, news_msg)
            return

        analyzer = self._forex_analyzer if market == Market.FOREX else self._crypto_analyzer
        if analyzer is None:
            return

        signal = await analyzer.analyze(symbol, market)
        if signal is None:
            return

        signal.confidence = self._scorer.score(signal)

        if not self._scorer.meets_threshold(signal.confidence):
            await self._repo.log_signal(signal, accepted=False, reject_reason=f"Low confidence: {signal.confidence:.3f}")
            logger.debug("%s signal rejected (confidence %.3f < %.3f)", symbol, signal.confidence, settings.ai_min_confidence)
            return

        valid, reject_reason = self._risk.validate_signal(signal)
        if not valid:
            await self._repo.log_signal(signal, accepted=False, reject_reason=reject_reason)
            logger.debug("%s signal rejected: %s", symbol, reject_reason)
            return

        can_trade, reason = await self._risk.can_trade()
        if not can_trade:
            await self._repo.log_signal(signal, accepted=False, reject_reason=reason)
            return

        position_size = self._risk.calculate_position_size(signal, market)
        if position_size <= 0:
            await self._repo.log_signal(signal, accepted=False, reject_reason="Position size zero")
            return

        trade = self._risk.create_trade_record(signal, position_size)
        trade.metadata = {"features": signal.features}

        tm = self._forex_tm if market == Market.FOREX else self._crypto_tm
        if tm is None:
            return

        success = await tm.open_trade(trade)
        if success:
            await self._repo.log_signal(signal, accepted=True)
            logger.info(
                "TRADE EXECUTED: %s %s %s @ %.5f | SL=%.5f TP1=%.5f TP2=%.5f TP3=%.5f | Conf=%.2f Size=%.4f",
                signal.direction.value, symbol, signal.signal_type.value,
                trade.entry_price, trade.stop_loss, trade.tp1, trade.tp2, trade.tp3,
                signal.confidence, position_size,
            )
        else:
            await self._repo.log_signal(signal, accepted=False, reject_reason="Execution failed")

    async def _periodic_tasks(self, now: datetime) -> None:
        if self._last_retrain is None or (now - self._last_retrain).total_seconds() > settings.ai_retrain_interval_hours * 3600:
            await self._retrain_ai()
            self._last_retrain = now

        if self._last_snapshot is None or (now - self._last_snapshot).total_seconds() > 300:
            await self._save_snapshot()
            self._last_snapshot = now

    async def _retrain_ai(self) -> None:
        try:
            closed = await self._repo.get_closed_trades(limit=500)
            if len(closed) < 20:
                logger.info("Not enough closed trades for AI retraining (%d)", len(closed))
                return
            metrics = self._ai_model.train(closed)
            if metrics:
                await self._repo.save_ai_metrics(metrics)
                logger.info("AI model retrained: F1=%.3f", metrics.get("f1_score", 0))
        except Exception:
            logger.exception("AI retrain failed")

    async def _save_snapshot(self) -> None:
        if self._risk:
            try:
                forex_count = len(self._forex_tm.open_trades) if self._forex_tm else 0
                crypto_count = len(self._crypto_tm.open_trades) if self._crypto_tm else 0
                self._risk.account.open_trades = forex_count + crypto_count
                self._risk.account.session_trades = await self._repo.get_session_trade_count()
                await self._repo.save_account_snapshot(self._risk.account)
            except Exception:
                logger.exception("Snapshot save failed")

    async def _init_feeds(self) -> None:
        if settings.forex_symbols:
            mt5_feed = MT5DataFeed()
            ok = await mt5_feed.initialize()
            if ok:
                self._forex_feed = mt5_feed if settings.trading_mode == TradingMode.LIVE else PaperDataFeed(mt5_feed)
            else:
                logger.warning("MT5 feed unavailable — forex disabled")

            if self._forex_feed:
                self._forex_cm = CandleManager(self._forex_feed)
                self._forex_analyzer = MTFAnalyzer(self._forex_cm)

        if settings.crypto_symbols:
            binance_feed = BinanceDataFeed()
            ok = await binance_feed.initialize()
            if ok:
                self._crypto_feed = binance_feed if settings.trading_mode == TradingMode.LIVE else PaperDataFeed(binance_feed)
            else:
                logger.warning("Binance feed unavailable — crypto disabled")

            if self._crypto_feed:
                self._crypto_cm = CandleManager(self._crypto_feed)
                self._crypto_analyzer = MTFAnalyzer(self._crypto_cm)

    async def _init_executors(self) -> None:
        if settings.trading_mode == TradingMode.PAPER:
            self._forex_executor = PaperExecutor()
            self._crypto_executor = PaperExecutor()
            logger.info("Paper executors initialized")
            return

        if self._forex_feed:
            mt5_exec = MT5Executor()
            ok = await mt5_exec.initialize()
            self._forex_executor = mt5_exec if ok else PaperExecutor()

        if self._crypto_feed:
            binance_exec = BinanceExecutor()
            ok = await binance_exec.initialize()
            self._crypto_executor = binance_exec if ok else PaperExecutor()

    async def _init_trade_managers(self) -> None:
        if self._forex_executor and self._forex_feed:
            self._forex_tm = TradeManager(
                self._forex_executor, self._forex_feed, self._risk, self._repo,
            )

        if self._crypto_executor and self._crypto_feed:
            self._crypto_tm = TradeManager(
                self._crypto_executor, self._crypto_feed, self._risk, self._repo,
            )

    async def _shutdown(self) -> None:
        logger.info("Shutting down engine...")
        if self._forex_tm:
            count = await self._forex_tm.close_all("shutdown")
            logger.info("Closed %d forex trades", count)
        if self._crypto_tm:
            count = await self._crypto_tm.close_all("shutdown")
            logger.info("Closed %d crypto trades", count)
        await self._save_snapshot()
        await close_db()
        logger.info("Engine shutdown complete")

    def get_status(self) -> Dict:
        account = self._risk.account if self._risk else None
        return {
            "running": self._running,
            "mode": settings.trading_mode.value,
            "cycle_count": self._cycle_count,
            "session": self._session_filter.get_session().value,
            "account": {
                "balance": account.balance if account else 0,
                "equity": account.equity if account else 0,
                "total_pnl": account.total_pnl if account else 0,
                "drawdown_pct": account.current_drawdown_pct if account else 0,
                "max_drawdown": account.max_drawdown if account else 0,
                "win_rate": account.win_rate if account else 0,
                "total_trades": account.total_trades if account else 0,
                "open_trades": account.open_trades if account else 0,
            } if account else {},
            "forex_symbols": settings.forex_symbols,
            "crypto_symbols": settings.crypto_symbols,
            "ai_trained": self._ai_model.is_trained,
            "upcoming_news": len(self._news_filter.upcoming_events),
        }
