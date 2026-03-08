"""
Bot Orchestrator — Main 24/7 trading loop.

Coordinates:
1. Market data fetching (H1/M15/M5 for all symbols)
2. Multi-timeframe analysis
3. AI confidence scoring
4. Session + news filtering
5. Risk pre-check
6. Signal generation
7. Order execution
8. Trade management (TP/SL/BE monitoring)
9. Performance snapshotting
10. AI model retraining (every 24h)
"""

import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, Dict, List
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.database import (
    Trade, Signal, PerformanceSnapshot, BotSession, MarketData,
    TradeStatus, SignalStatus, TradingMode, MarketType, TradeDirection,
    AsyncSessionLocal, init_db,
)
from src.connectors.mt5_connector import MT5Connector
from src.connectors.binance_connector import BinanceConnector
from src.strategy.multi_timeframe import MultiTimeframeAnalyzer, MTFSignal
from src.ai.classifier import TradeClassifier
from src.ai.feature_engineering import extract_features, FEATURE_NAMES
from src.risk.risk_manager import RiskManager
from src.execution.mt5_executor import MT5Executor
from src.execution.binance_executor import BinanceExecutor
from src.trade_management.manager import TradeManager
from src.filters.session_filter import SessionFilter
from src.filters.news_filter import NewsFilter
from config.settings import settings, TradingMode as TradingModeEnum


# Module-level singleton
_orchestrator: Optional["BotOrchestrator"] = None


def get_orchestrator() -> Optional["BotOrchestrator"]:
    return _orchestrator


def get_orchestrator_status() -> dict:
    if _orchestrator is None:
        return {}
    return _orchestrator.get_status()


class BotOrchestrator:
    """
    Central coordinator for the trading bot.
    Runs an async event loop scanning all symbols on each M5 close.
    """

    SCAN_INTERVAL_SECONDS = 60       # Check every 60 seconds
    SNAPSHOT_INTERVAL_SECONDS = 3600  # Performance snapshot every hour
    RETRAIN_INTERVAL_HOURS = 24       # Retrain AI every 24 hours

    def __init__(self):
        self._running = False
        self._paused = False
        self._start_time: Optional[datetime] = None
        self._last_scan: Optional[datetime] = None
        self._last_snapshot: Optional[datetime] = None
        self._last_retrain: Optional[datetime] = None
        self._current_session_id: Optional[str] = None

        paper_mode = settings.trading_mode == TradingModeEnum.PAPER

        # ── Components ────────────────────────────────────────────────────────
        self.mt5_connector = MT5Connector()
        self.binance_connector = BinanceConnector()

        self.mt5_executor = MT5Executor(paper_mode=paper_mode)
        self.binance_executor = BinanceExecutor(paper_mode=paper_mode)

        self.mtf_analyzer = MultiTimeframeAnalyzer()
        self.ai_classifier = TradeClassifier()
        self.risk_manager = RiskManager()
        self.session_filter = SessionFilter()
        self.news_filter = NewsFilter()
        self.trade_manager = TradeManager(
            self.mt5_executor, self.binance_executor, self.risk_manager
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        global _orchestrator
        _orchestrator = self

        logger.info(f"Bot starting | mode={settings.trading_mode.value}")
        await init_db()
        await self._connect_brokers()
        await self._start_session()

        self._running = True
        self._start_time = datetime.now(tz=timezone.utc)

        await asyncio.gather(
            self._main_loop(),
            self._trade_management_loop(),
            self._snapshot_loop(),
        )

    async def stop(self) -> None:
        logger.info("Bot stopping...")
        self._running = False
        await self._end_session()
        await self.mt5_connector.disconnect()
        await self.binance_connector.disconnect()
        logger.info("Bot stopped")

    def pause(self) -> None:
        self._paused = True
        logger.info("Bot paused — no new trades will be placed")

    def resume(self) -> None:
        self._paused = False
        logger.info("Bot resumed")

    # ── Main Trading Loop ─────────────────────────────────────────────────────

    async def _main_loop(self) -> None:
        logger.info("Main trading loop started")
        while self._running:
            try:
                if not self._paused:
                    await self._scan_all_symbols()
                self._last_scan = datetime.now(tz=timezone.utc)

                # Retrain AI if due
                if self._should_retrain():
                    await self.retrain_ai()

            except Exception as e:
                logger.error(f"Main loop error: {e}", exc_info=True)

            await asyncio.sleep(self.SCAN_INTERVAL_SECONDS)

    async def _trade_management_loop(self) -> None:
        """Monitor open trades every 10 seconds for TP/SL/BE."""
        logger.info("Trade management loop started")
        while self._running:
            try:
                current_prices = await self._get_current_prices()
                if current_prices:
                    await self.trade_manager.manage_open_trades(current_prices)

                # Check max drawdown
                check = self.risk_manager.pre_trade_check()
                if not check.approved and "drawdown" in (check.rejection_reason or ""):
                    logger.critical("MAX DRAWDOWN BREACHED — emergency closing all trades")
                    await self.trade_manager.emergency_close_all("max_drawdown")
                    self.pause()

            except Exception as e:
                logger.error(f"Trade management loop error: {e}", exc_info=True)

            await asyncio.sleep(10)

    async def _snapshot_loop(self) -> None:
        """Save performance snapshots periodically."""
        while self._running:
            await asyncio.sleep(self.SNAPSHOT_INTERVAL_SECONDS)
            try:
                await self._save_performance_snapshot()
            except Exception as e:
                logger.error(f"Snapshot error: {e}")

    # ── Symbol Scanning ───────────────────────────────────────────────────────

    async def _scan_all_symbols(self) -> None:
        """Scan all configured symbols for trading opportunities."""
        now = datetime.now(tz=timezone.utc)

        # ─── Session Filter ───────────────────────────────────────────────────
        session_check = self.session_filter.check(now)
        if not session_check.allowed:
            logger.debug(f"Outside trading session: {session_check.reason}")
            return

        logger.info(
            f"Scanning {len(settings.mt5_symbol_list)} forex + "
            f"{len(settings.binance_symbol_list)} crypto symbols | "
            f"session={session_check.session.value}"
        )

        # Scan forex symbols
        for symbol in settings.mt5_symbol_list:
            try:
                await self._scan_symbol(symbol, "forex", self.mt5_connector)
            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")

        # Scan crypto symbols
        for symbol in settings.binance_symbol_list:
            try:
                await self._scan_symbol(symbol, "crypto", self.binance_connector)
            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")

    async def _scan_symbol(self, symbol: str, market: str, connector) -> None:
        """Run full analysis pipeline for a single symbol."""
        # ─── Fetch OHLCV data ─────────────────────────────────────────────────
        htf_df = await connector.get_ohlcv(symbol, settings.htf_timeframe, count=200)
        mtf_df = await connector.get_ohlcv(symbol, settings.mtf_timeframe, count=200)
        ltf_df = await connector.get_ohlcv(symbol, settings.ltf_timeframe, count=100)

        if any(df.empty for df in [htf_df, mtf_df, ltf_df]):
            logger.debug(f"Incomplete data for {symbol}")
            return

        # ─── Multi-Timeframe Analysis ─────────────────────────────────────────
        signal = await self.mtf_analyzer.analyse(symbol, market, htf_df, mtf_df, ltf_df)

        if not signal.valid:
            logger.debug(f"{symbol}: {signal.rejection_reason}")
            return

        # ─── News Filter ──────────────────────────────────────────────────────
        news_check = await self.news_filter.check(symbol, now=datetime.now(tz=timezone.utc))

        # ─── AI Confidence Scoring ────────────────────────────────────────────
        ai_confidence = self.ai_classifier.predict_confidence(signal)

        if ai_confidence < settings.min_confidence:
            logger.debug(
                f"{symbol}: AI confidence too low {ai_confidence:.2%} < {settings.min_confidence:.2%}"
            )
            return

        # ─── Risk Pre-Check ───────────────────────────────────────────────────
        risk_check = self.risk_manager.pre_trade_check()
        if not risk_check.approved:
            logger.warning(f"Risk check failed: {risk_check.rejection_reason}")
            return

        # ─── News Check ───────────────────────────────────────────────────────
        if not news_check.clear:
            logger.info(f"{symbol}: Blocked by news — {news_check.reason}")
            await self._save_signal(signal, ai_confidence, session_check=None, news_clear=False)
            return

        # ─── Position Sizing ──────────────────────────────────────────────────
        position = self._calculate_position(signal, market, connector)
        if not position or not position.valid:
            logger.warning(f"{symbol}: Invalid position size — {position.rejection_reason if position else 'N/A'}")
            return

        logger.info(
            f"SIGNAL | {symbol} {signal.direction.upper()} | "
            f"confidence={ai_confidence:.2%} rr={signal.risk_reward:.2f} "
            f"lot={position.lot_size} entry={signal.entry_price:.5f}"
        )

        # ─── Save Signal ──────────────────────────────────────────────────────
        signal_record = await self._save_signal(
            signal, ai_confidence,
            session_check=session_filter_value := self.session_filter.check(),
            news_clear=True,
        )

        # ─── Execute Trade ────────────────────────────────────────────────────
        await self._execute_trade(signal, position, market, ai_confidence, signal_record)

    def _calculate_position(self, signal: MTFSignal, market: str, connector):
        """Calculate position size based on market type."""
        if market == "forex":
            return self.risk_manager.calculate_position_size_forex(
                symbol=signal.symbol,
                entry=signal.entry_price,
                stop_loss=signal.stop_loss,
            )
        else:
            return self.risk_manager.calculate_position_size_crypto(
                symbol=signal.symbol,
                entry=signal.entry_price,
                stop_loss=signal.stop_loss,
            )

    async def _execute_trade(
        self,
        signal: MTFSignal,
        position,
        market: str,
        ai_confidence: float,
        signal_record,
    ) -> None:
        """Execute the trade on the appropriate exchange."""
        executor = self.mt5_executor if market == "forex" else self.binance_executor
        direction_str = signal.direction  # "bullish" or "bearish"
        exec_direction = "long" if direction_str == "bullish" else "short"

        # Update account balance before sizing
        account = await (self.mt5_connector if market == "forex" else self.binance_connector).get_account_info()
        if account:
            self.risk_manager.update_balance(account.balance)

        result = await executor.open_trade(
            symbol=signal.symbol,
            direction=exec_direction,
            lot_size=position.lot_size,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            tp1=signal.tp1,
        )

        if not result.success:
            logger.error(f"Trade execution failed for {signal.symbol}: {result.error}")
            return

        # ─── Record trade in database ─────────────────────────────────────────
        features = extract_features(signal)
        ai_features_dict = {name: float(val) for name, val in zip(FEATURE_NAMES, features)}

        now = datetime.now(tz=timezone.utc)
        db_trade = Trade(
            symbol=signal.symbol,
            market=MarketType(market),
            direction=TradeDirection(exec_direction),
            status=TradeStatus.OPEN,
            mode=TradingMode(settings.trading_mode.value),
            entry_price=Decimal(str(result.executed_price or signal.entry_price)),
            stop_loss=Decimal(str(signal.stop_loss)),
            tp1=Decimal(str(signal.tp1)),
            tp2=Decimal(str(signal.tp2)),
            tp3=Decimal(str(signal.tp3)),
            lot_size=Decimal(str(position.lot_size)),
            risk_amount=Decimal(str(position.risk_amount)),
            account_balance_at_open=Decimal(str(self.risk_manager._current_balance)),
            ai_confidence=Decimal(str(round(ai_confidence, 4))),
            signal_id=signal_record.id if signal_record else None,
            broker_ticket=result.broker_ticket,
            open_time=now,
            metadata_={"ai_features": ai_features_dict, "rr": signal.risk_reward},
        )

        async with AsyncSessionLocal() as session:
            session.add(db_trade)
            await session.commit()

        self.risk_manager.record_trade_open(position.risk_amount)
        logger.info(
            f"TRADE OPENED | {signal.symbol} {exec_direction.upper()} | "
            f"lot={position.lot_size} entry={result.executed_price} "
            f"sl={signal.stop_loss} ticket={result.broker_ticket}"
        )

    # ── Helper Methods ────────────────────────────────────────────────────────

    async def _get_current_prices(self) -> Dict[str, float]:
        prices = {}
        for symbol in settings.mt5_symbol_list:
            try:
                tick = await self.mt5_connector.get_tick(symbol)
                if tick:
                    prices[symbol] = (tick.bid + tick.ask) / 2
            except Exception:
                pass

        for symbol in settings.binance_symbol_list:
            try:
                tick = await self.binance_connector.get_tick(symbol)
                if tick:
                    prices[symbol] = tick.last
            except Exception:
                pass

        return prices

    async def _save_signal(
        self, signal: MTFSignal, confidence: float,
        session_check, news_clear: bool
    ):
        """Persist a signal record to the database."""
        features = extract_features(signal)
        ai_features_dict = {name: float(val) for name, val in zip(FEATURE_NAMES, features)}

        session_name = session_check.session.value if session_check else None
        db_signal = Signal(
            symbol=signal.symbol,
            market=MarketType(signal.market),
            direction=TradeDirection("long" if signal.direction == "bullish" else "short"),
            status=SignalStatus.PENDING,
            htf_bias=signal.htf.trend,
            mtf_trend=signal.mtf.trend,
            ltf_entry=signal.ltf.trend,
            liquidity_swept=signal.ltf.sweep.detected,
            bos_confirmed=signal.mtf.bos.detected,
            pullback_valid=signal.ltf.pullback.valid,
            entry_price=Decimal(str(signal.entry_price)) if signal.entry_price else None,
            stop_loss=Decimal(str(signal.stop_loss)) if signal.stop_loss else None,
            tp1=Decimal(str(signal.tp1)) if signal.tp1 else None,
            tp2=Decimal(str(signal.tp2)) if signal.tp2 else None,
            tp3=Decimal(str(signal.tp3)) if signal.tp3 else None,
            atr_value=Decimal(str(signal.atr)) if signal.atr else None,
            ai_confidence=Decimal(str(round(confidence, 4))),
            ai_features=ai_features_dict,
            session=session_name,
            news_clear=news_clear,
            expires_at=datetime.now(tz=timezone.utc) + timedelta(minutes=30),
        )

        async with AsyncSessionLocal() as session:
            session.add(db_signal)
            await session.commit()
            await session.refresh(db_signal)

        return db_signal

    async def _save_performance_snapshot(self) -> None:
        """Save current performance metrics to the database."""
        risk_status = self.risk_manager.get_status()
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select as sa_select
            result = await db.execute(
                sa_select(Trade).where(Trade.status == TradeStatus.CLOSED)
            )
            closed = result.scalars().all()

            total = len(closed)
            winners = [t for t in closed if float(t.realized_pnl) > 0]
            total_pnl = sum(float(t.realized_pnl) for t in closed)
            gross_profit = sum(float(t.realized_pnl) for t in winners)
            gross_loss = abs(sum(float(t.realized_pnl) for t in closed if float(t.realized_pnl) < 0))
            pf = gross_profit / gross_loss if gross_loss > 0 else None
            win_rate = len(winners) / total if total > 0 else None

            snap = PerformanceSnapshot(
                mode=TradingMode(settings.trading_mode.value),
                balance=Decimal(str(risk_status["current_balance"])),
                equity=Decimal(str(risk_status["current_balance"])),
                total_trades=total,
                winning_trades=len(winners),
                losing_trades=total - len(winners),
                total_pnl=Decimal(str(round(total_pnl, 2))),
                max_drawdown=Decimal(str(round(risk_status["current_drawdown_pct"] * risk_status["current_balance"], 2))),
                win_rate=Decimal(str(round(win_rate, 4))) if win_rate else None,
                profit_factor=Decimal(str(round(pf, 4))) if pf else None,
            )
            db.add(snap)
            await db.commit()

        logger.debug("Performance snapshot saved")

    async def _connect_brokers(self) -> None:
        """Connect to all configured brokers."""
        mt5_ok = await self.mt5_connector.connect()
        binance_ok = await self.binance_connector.connect()
        await self.binance_executor.initialize()
        logger.info(f"Brokers: MT5={mt5_ok} Binance={binance_ok}")

    async def _start_session(self) -> None:
        session = BotSession(
            mode=TradingMode(settings.trading_mode.value),
            status="active",
        )
        async with AsyncSessionLocal() as db:
            db.add(session)
            await db.commit()
            await db.refresh(session)
            self._current_session_id = str(session.id)
        logger.info(f"Bot session started | id={self._current_session_id}")

    async def _end_session(self) -> None:
        if not self._current_session_id:
            return
        from sqlalchemy import update
        risk = self.risk_manager.get_status()
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(BotSession)
                .where(BotSession.id == self._current_session_id)
                .values(
                    end_time=datetime.now(tz=timezone.utc),
                    status="stopped",
                    session_pnl=Decimal(str(risk["session_pnl"])),
                    trades_taken=risk["session_trades"],
                )
            )
            await db.commit()

    def _should_retrain(self) -> bool:
        if self._last_retrain is None:
            return False  # Don't retrain on first run; need data first
        elapsed = (datetime.now(tz=timezone.utc) - self._last_retrain).total_seconds() / 3600
        return elapsed >= self.RETRAIN_INTERVAL_HOURS

    async def retrain_ai(self) -> dict:
        """Fetch historical trades and retrain the AI classifier."""
        logger.info("Retraining AI classifier...")
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select as sa_select
            result = await db.execute(
                sa_select(Trade)
                .where(Trade.status == TradeStatus.CLOSED)
                .order_by(Trade.close_time.desc())
                .limit(1000)
            )
            trades = result.scalars().all()

        trade_dicts = [
            {
                "ai_features": t.metadata_.get("ai_features", {}),
                "realized_pnl": float(t.realized_pnl),
            }
            for t in trades
        ]

        X, y = self.ai_classifier.build_training_data_from_trades(trade_dicts)
        if len(X) == 0:
            return {"error": "No training data available"}

        result = self.ai_classifier.train(X, y)
        self._last_retrain = datetime.now(tz=timezone.utc)
        logger.info(f"AI retrain complete: {result}")
        return result

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        uptime = 0.0
        if self._start_time:
            uptime = (datetime.now(tz=timezone.utc) - self._start_time).total_seconds()

        return {
            "running": self._running,
            "paused": self._paused,
            "uptime_seconds": uptime,
            "last_scan": self._last_scan.isoformat() if self._last_scan else None,
            "mode": settings.trading_mode.value,
            "ai_status": self.ai_classifier.get_status(),
            "risk_status": self.risk_manager.get_status(),
            "session_id": self._current_session_id,
        }
