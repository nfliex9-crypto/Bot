"""
Trading Bot Core.

The main orchestrator that:
1. Initializes all components
2. Runs the market scanner on a schedule
3. Executes trades from valid signals
4. Monitors open positions
5. Manages trade lifecycle (TP hits, BE, SL)
6. Handles graceful shutdown
"""
import asyncio
import signal as os_signal
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app.brokers.mt5_broker import MT5Broker
from app.brokers.binance_broker import BinanceBroker
from app.brokers.base import OrderResult
from app.core.strategy.multi_timeframe import MultiTimeframeAnalyzer
from app.core.ai.classifier import TradeClassifier
from app.core.risk_manager import RiskManager
from app.core.trade_manager import TradeManager, TradeUpdate
from app.core.session_filter import SessionFilter
from app.core.news_filter import NewsFilter
from app.bot.scanner import MarketScanner, ScanResult
from app.database import AsyncSessionLocal
from app.models.trade import Trade, TradeStatus, TradeDirection
from app.models.signal import Signal, SignalStatus
from app.schemas.trade import TradeCreate
from app.schemas.signal import SignalCreate
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("trading_bot")

UTC = timezone.utc


class BotState:
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"


class TradingBot:
    """
    24/7 AI-powered trading bot.

    Manages the complete trade lifecycle:
    - Market scanning → Signal generation → Trade execution → Position monitoring
    """

    def __init__(self):
        self.state = BotState.STOPPED
        self._running = False
        self._scan_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None

        # Components (initialized in start())
        self.mt5_broker: Optional[MT5Broker] = None
        self.binance_broker: Optional[BinanceBroker] = None
        self.mtf_analyzer: Optional[MultiTimeframeAnalyzer] = None
        self.classifier: Optional[TradeClassifier] = None
        self.risk_manager: Optional[RiskManager] = None
        self.trade_manager: Optional[TradeManager] = None
        self.session_filter: Optional[SessionFilter] = None
        self.news_filter: Optional[NewsFilter] = None
        self.scanner: Optional[MarketScanner] = None

        # Stats
        self._start_time: Optional[datetime] = None
        self._signals_generated: int = 0
        self._trades_executed: int = 0
        self._trades_closed: int = 0
        self._total_pnl: float = 0.0
        self._errors: int = 0

    async def start(self):
        """Initialize all components and start the bot."""
        if self._running:
            logger.warning("Bot already running")
            return

        logger.info("=" * 60)
        logger.info(f"Starting {settings.APP_NAME} v{settings.VERSION}")
        logger.info(f"Trading mode: {settings.TRADING_MODE.upper()}")
        logger.info("=" * 60)

        self.state = BotState.STARTING
        self._start_time = datetime.now(UTC)

        try:
            await self._init_components()
            await self._connect_brokers()

            self._running = True
            self.state = BotState.RUNNING

            # Start background tasks
            self._scan_task = asyncio.create_task(self._scan_loop())
            self._monitor_task = asyncio.create_task(self._monitor_loop())
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            logger.info("Bot started successfully. Running 24/7...")

        except Exception as e:
            self.state = BotState.ERROR
            logger.error(f"Bot startup failed: {e}", exc_info=True)
            raise

    async def stop(self):
        """Gracefully stop the bot."""
        if not self._running:
            return

        logger.info("Stopping trading bot...")
        self.state = BotState.STOPPING
        self._running = False

        # Cancel background tasks
        for task in [self._scan_task, self._monitor_task, self._heartbeat_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Disconnect brokers
        if self.mt5_broker:
            await self.mt5_broker.disconnect()
        if self.binance_broker:
            await self.binance_broker.disconnect()

        self.state = BotState.STOPPED
        logger.info("Bot stopped.")

    async def pause(self):
        """Pause scanning without stopping the bot."""
        self.state = BotState.PAUSED
        logger.info("Bot paused")

    async def resume(self):
        """Resume scanning after pause."""
        if self.state == BotState.PAUSED:
            self.state = BotState.RUNNING
            logger.info("Bot resumed")

    # --- Initialization ---

    async def _init_components(self):
        """Initialize all trading components."""
        logger.info("Initializing components...")

        self.mt5_broker = MT5Broker(paper_mode=settings.is_paper)
        self.binance_broker = BinanceBroker(
            api_key=settings.BINANCE_API_KEY,
            secret_key=settings.BINANCE_SECRET_KEY,
            testnet=settings.BINANCE_TESTNET,
            paper_mode=settings.is_paper,
        )
        self.mtf_analyzer = MultiTimeframeAnalyzer()
        self.classifier = TradeClassifier(
            model_path=settings.MODEL_PATH,
            min_confidence=settings.MIN_CONFIDENCE,
        )
        self.risk_manager = RiskManager(
            account_balance=settings.ACCOUNT_BALANCE,
            risk_per_trade=settings.RISK_PER_TRADE,
            max_drawdown=settings.MAX_DRAWDOWN,
            max_trades_per_session=settings.MAX_TRADES_PER_SESSION,
        )
        self.trade_manager = TradeManager(
            tp1_ratio=settings.TP1_RATIO,
            tp2_ratio=settings.TP2_RATIO,
            tp3_ratio=settings.TP3_RATIO,
            breakeven_after_tp1=settings.BREAKEVEN_AFTER_TP1,
        )
        self.session_filter = SessionFilter()
        self.news_filter = NewsFilter()

        self.scanner = MarketScanner(
            forex_broker=self.mt5_broker,
            crypto_broker=self.binance_broker,
            mtf_analyzer=self.mtf_analyzer,
            classifier=self.classifier,
            session_filter=self.session_filter,
            news_filter=self.news_filter,
            risk_manager=self.risk_manager,
        )

        # Initial news fetch
        await self.news_filter.refresh_events()
        logger.info("All components initialized")

    async def _connect_brokers(self):
        """Connect to all brokers."""
        logger.info("Connecting to brokers...")
        mt5_ok = await self.mt5_broker.connect()
        binance_ok = await self.binance_broker.connect()

        if not mt5_ok:
            logger.warning("MT5 broker connection failed, using paper mode")
        if not binance_ok:
            logger.warning("Binance broker connection failed, using paper mode")

        # Update risk manager with real account balance
        try:
            acc = await self.mt5_broker.get_account_info()
            if acc.balance > 0:
                self.risk_manager.update_balance(acc.balance)
        except Exception:
            pass

    # --- Background Loops ---

    async def _scan_loop(self):
        """Main scanning loop - runs every SCAN_INTERVAL_SECONDS."""
        logger.info(
            f"Scanner started | interval={settings.SCAN_INTERVAL_SECONDS}s "
            f"mode={settings.TRADING_MODE.value}"
        )

        while self._running:
            try:
                if self.state == BotState.RUNNING:
                    try:
                        from app.monitoring.metrics import get_metrics
                        get_metrics().record_scan()
                    except Exception:
                        pass

                    results = await self.scanner.scan_all()

                    if results:
                        logger.info(
                            f"SIGNAL SCAN | {len(results)} valid setup(s) found "
                            f"| top={results[0].symbol} "
                            f"conf={results[0].prediction.confidence:.3f}",
                            extra={"trade_log": True},
                        )

                    # Execute valid setups (up to remaining session trade allowance)
                    for result in results:
                        risk_status = self.risk_manager.check_risk_limits()
                        if not risk_status.can_trade:
                            logger.info(f"Risk limit reached: {risk_status.reason}")
                            break
                        await self._execute_setup(result)

                await asyncio.sleep(settings.SCAN_INTERVAL_SECONDS)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._errors += 1
                logger.error(f"Scan loop error: {type(e).__name__}: {e}", exc_info=True)
                try:
                    from app.monitoring.metrics import get_metrics
                    get_metrics().record_error("scan_loop")
                except Exception:
                    pass
                await asyncio.sleep(10)

    async def _monitor_loop(self):
        """Monitor open positions loop - runs every 10 seconds."""
        logger.info("Position monitor started")

        while self._running:
            try:
                if self.state == BotState.RUNNING:
                    await self._monitor_open_trades()
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._errors += 1
                logger.error(f"Monitor loop error: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def _heartbeat_loop(self):
        """Heartbeat loop - logs bot status periodically."""
        while self._running:
            try:
                uptime = datetime.now(UTC) - self._start_time if self._start_time else timedelta(0)
                logger.info(
                    f"[HEARTBEAT] State={self.state} Uptime={str(uptime).split('.')[0]} "
                    f"Signals={self._signals_generated} Trades={self._trades_executed} "
                    f"PnL={self._total_pnl:+.2f} Errors={self._errors}"
                )
                await asyncio.sleep(settings.HEARTBEAT_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(30)

    # --- Trade Execution ---

    async def _execute_setup(self, result: ScanResult):
        """Execute a validated trade setup."""
        if not result.is_valid or result.mtf.m5_entry is None:
            return

        entry = result.mtf.m5_entry
        symbol = result.symbol
        market_type = result.market_type

        logger.info(
            f"Executing setup: {symbol} {entry.direction} "
            f"entry={entry.entry_price:.5f} sl={entry.stop_loss:.5f} "
            f"tp1={entry.take_profit_1:.5f} conf={result.prediction.confidence:.2f}"
        )

        # Calculate position size
        broker = self.mt5_broker if market_type == "forex" else self.binance_broker
        position_size = self.risk_manager.calculate_position_size(
            symbol=symbol,
            entry_price=entry.entry_price,
            stop_loss=entry.stop_loss,
            market_type=market_type,
        )

        if not position_size.valid or position_size.lot_size <= 0:
            logger.warning(f"Invalid position size for {symbol}: {position_size.rejection_reason}")
            return

        # Save signal to DB
        signal_id = await self._save_signal(result, entry)

        # Place order
        order_result = await broker.place_order(
            symbol=symbol,
            direction=entry.direction,
            lot_size=position_size.lot_size,
            stop_loss=entry.stop_loss,
            take_profit=entry.take_profit_1,  # Initial TP (TP1)
            comment=f"AIBot|{result.prediction.confidence:.2f}",
        )

        if not order_result.success:
            logger.error(f"Order execution failed for {symbol}: {order_result.error}")
            await self._update_signal_status(signal_id, SignalStatus.REJECTED, order_result.error)
            return

        # Save trade to DB
        trade_id = await self._save_trade(
            result=result,
            entry=entry,
            order_result=order_result,
            position_size=position_size,
            signal_id=signal_id,
        )

        # Update counters
        self.risk_manager.increment_session_trades()
        self._trades_executed += 1
        self._signals_generated += 1

        await self._update_signal_status(signal_id, SignalStatus.EXECUTED)

        logger.info(
            f"TRADE EXECUTED | {settings.TRADING_MODE.value.upper()} | "
            f"symbol={symbol} direction={entry.direction} "
            f"lots={position_size.lot_size} entry={entry.entry_price:.5f} "
            f"sl={entry.stop_loss:.5f} tp1={entry.take_profit_1:.5f} "
            f"risk=${position_size.risk_amount:.2f} "
            f"confidence={result.prediction.confidence:.3f} "
            f"ticket={order_result.ticket} signal_id={signal_id}",
            extra={"trade_log": True},
        )

        # Record in metrics collector
        try:
            from app.monitoring.metrics import get_metrics
            m = get_metrics()
            m.record_trade_open(
                trade_id=trade_id or 0,
                symbol=symbol,
                direction=entry.direction,
                entry_price=order_result.entry_price or entry.entry_price,
                intended_price=entry.entry_price,
                ai_confidence=result.prediction.confidence,
                market=market_type,
                mode=settings.TRADING_MODE.value,
            )
            m.record_signal(symbol, "executed")
        except Exception:
            pass

    # --- Position Monitoring ---

    async def _monitor_open_trades(self):
        """Check all open trades against current prices."""
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            result = await db.execute(
                select(Trade).where(Trade.status == TradeStatus.OPEN)
            )
            open_trades = result.scalars().all()

        if not open_trades:
            return

        for trade in open_trades:
            try:
                await self._check_trade_levels(trade)
            except Exception as e:
                logger.error(f"Error monitoring trade {trade.id}: {e}")

    async def _check_trade_levels(self, trade: Trade):
        """Check a single trade's current price against its levels."""
        broker = self.mt5_broker if trade.market_type == "forex" else self.binance_broker

        tick = await broker.get_tick(trade.symbol)
        if tick is None:
            return

        current_price = tick.bid if trade.direction == TradeDirection.LONG else tick.ask

        update = self.trade_manager.check_trade(
            trade_id=trade.id,
            direction=trade.direction.value,
            entry_price=trade.entry_price,
            current_price=current_price,
            stop_loss=trade.stop_loss,
            take_profit_1=trade.take_profit_1,
            take_profit_2=trade.take_profit_2,
            take_profit_3=trade.take_profit_3,
            tp1_hit=trade.tp1_hit,
            tp2_hit=trade.tp2_hit,
            tp3_hit=trade.tp3_hit,
            breakeven_moved=trade.breakeven_moved,
            lot_size=trade.lot_size,
        )

        if update.action == "none":
            # Just update current price in DB
            await self._update_trade_price(trade.id, current_price)
            return

        await self._process_trade_update(trade, update, broker, current_price)

    async def _process_trade_update(
        self,
        trade: Trade,
        update: TradeUpdate,
        broker,
        current_price: float,
    ):
        """Apply a trade update (partial close, full close, BE move)."""
        logger.info(
            f"Trade {trade.id} {trade.symbol}: action={update.action} "
            f"reason={update.reason}"
        )

        if update.action in ("close_full", "close_partial"):
            close_lots = trade.lot_size * update.close_pct if update.close_pct < 1.0 else None

            close_result = await broker.close_order(
                ticket=trade.ticket or str(trade.id),
                lot_size=close_lots,
            )

            if close_result.success:
                pnl = self.trade_manager.calculate_unrealized_pnl(
                    direction=trade.direction.value,
                    entry_price=trade.entry_price,
                    current_price=current_price,
                    lot_size=trade.lot_size * update.close_pct,
                    market_type=trade.market_type,
                    symbol=trade.symbol,
                )
                await self._update_trade_after_close(trade, update, current_price, pnl)
                self.risk_manager.record_trade_pnl(pnl)
                self._total_pnl += pnl

                if update.action == "close_full":
                    self._trades_closed += 1

        if update.action == "move_be" or (update.new_sl and update.action == "close_partial"):
            if update.new_sl:
                await broker.modify_order(
                    ticket=trade.ticket or str(trade.id),
                    stop_loss=update.new_sl,
                )
                await self._update_trade_be(trade.id, update.new_sl)

    # --- Database Operations ---

    async def _save_signal(self, result: ScanResult, entry) -> Optional[int]:
        """Save a signal to the database."""
        try:
            async with AsyncSessionLocal() as db:
                signal = Signal(
                    symbol=result.symbol,
                    market_type=result.market_type,
                    direction=entry.direction,
                    entry_price=entry.entry_price,
                    stop_loss=entry.stop_loss,
                    take_profit_1=entry.take_profit_1,
                    take_profit_2=entry.take_profit_2,
                    take_profit_3=entry.take_profit_3,
                    atr=entry.atr,
                    h1_bias=result.mtf.h1_bias,
                    m15_trend=result.mtf.m15_trend,
                    m5_signal=entry.direction,
                    liquidity_sweep_detected=result.mtf.m5_sweep is not None,
                    bos_detected=result.mtf.m5_bos is not None,
                    pullback_entry=True,
                    ai_confidence=result.prediction.confidence,
                    ai_features=result.prediction.feature_importance,
                    session=result.session,
                    news_clear=result.news_clear,
                    risk_reward=entry.risk_reward,
                )
                db.add(signal)
                await db.flush()
                signal_id = signal.id
                await db.commit()
                return signal_id
        except Exception as e:
            logger.error(f"Failed to save signal: {e}")
            return None

    async def _save_trade(
        self,
        result: ScanResult,
        entry,
        order_result: OrderResult,
        position_size,
        signal_id: Optional[int],
    ) -> Optional[int]:
        """Save a trade to the database."""
        try:
            async with AsyncSessionLocal() as db:
                direction = TradeDirection.LONG if entry.direction == "long" else TradeDirection.SHORT
                trade = Trade(
                    ticket=order_result.ticket,
                    symbol=result.symbol,
                    market_type=result.market_type,
                    direction=direction,
                    status=TradeStatus.OPEN,
                    trading_mode=settings.TRADING_MODE.value,
                    entry_price=order_result.entry_price or entry.entry_price,
                    current_price=order_result.entry_price or entry.entry_price,
                    lot_size=position_size.lot_size,
                    stop_loss=entry.stop_loss,
                    take_profit_1=entry.take_profit_1,
                    take_profit_2=entry.take_profit_2,
                    take_profit_3=entry.take_profit_3,
                    atr_at_entry=entry.atr,
                    risk_amount=position_size.risk_amount,
                    risk_reward_ratio=entry.risk_reward,
                    session=result.session,
                    ai_confidence=result.prediction.confidence,
                    signal_id=signal_id,
                    strategy="Sweep+BOS+Pullback",
                    timeframe=settings.M5_TIMEFRAME,
                    opened_at=datetime.now(UTC),
                )
                db.add(trade)
                await db.flush()
                trade_id = trade.id
                await db.commit()
                return trade_id
        except Exception as e:
            logger.error(f"Failed to save trade: {e}")
            return None

    async def _update_signal_status(
        self,
        signal_id: Optional[int],
        status: SignalStatus,
        reason: Optional[str] = None,
    ):
        if signal_id is None:
            return
        try:
            async with AsyncSessionLocal() as db:
                from sqlalchemy import update
                await db.execute(
                    update(Signal)
                    .where(Signal.id == signal_id)
                    .values(
                        status=status,
                        rejection_reason=reason,
                        executed_at=datetime.now(UTC) if status == SignalStatus.EXECUTED else None,
                    )
                )
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to update signal: {e}")

    async def _update_trade_price(self, trade_id: int, current_price: float):
        try:
            async with AsyncSessionLocal() as db:
                from sqlalchemy import update
                await db.execute(
                    update(Trade)
                    .where(Trade.id == trade_id)
                    .values(current_price=current_price)
                )
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to update trade price: {e}")

    async def _update_trade_after_close(
        self,
        trade: Trade,
        update: TradeUpdate,
        close_price: float,
        pnl: float,
    ):
        try:
            async with AsyncSessionLocal() as db:
                from sqlalchemy import update as sql_update
                values = {
                    "current_price": close_price,
                    "pnl": (trade.pnl or 0.0) + pnl,
                }

                if update.tp_level == 1:
                    values["tp1_hit"] = True
                elif update.tp_level == 2:
                    values["tp2_hit"] = True
                elif update.tp_level == 3:
                    values["tp3_hit"] = True

                if update.action == "close_full":
                    values["status"] = TradeStatus.CLOSED
                    values["exit_price"] = close_price
                    values["closed_at"] = datetime.now(UTC)
                else:
                    values["status"] = TradeStatus.PARTIAL

                await db.execute(
                    sql_update(Trade).where(Trade.id == trade.id).values(**values)
                )
                await db.commit()

        except Exception as e:
            logger.error(f"Failed to update trade after close: {e}")

    async def _update_trade_be(self, trade_id: int, new_sl: float):
        try:
            async with AsyncSessionLocal() as db:
                from sqlalchemy import update
                await db.execute(
                    update(Trade)
                    .where(Trade.id == trade_id)
                    .values(breakeven_moved=True, stop_loss=new_sl, breakeven_price=new_sl)
                )
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to update break-even: {e}")

    # --- Status & Stats ---

    def get_status(self) -> dict:
        """Get current bot status."""
        uptime = None
        if self._start_time:
            uptime = str(datetime.now(UTC) - self._start_time).split(".")[0]

        session = self.session_filter.get_current_session() if self.session_filter else None

        return {
            "state": self.state,
            "trading_mode": settings.TRADING_MODE.value,
            "uptime": uptime,
            "start_time": self._start_time.isoformat() if self._start_time else None,
            "session": session.name if session else "unknown",
            "session_active": session.is_active if session else False,
            "signals_generated": self._signals_generated,
            "trades_executed": self._trades_executed,
            "trades_closed": self._trades_closed,
            "total_pnl": round(self._total_pnl, 2),
            "errors": self._errors,
            "risk": self.risk_manager.get_account_stats() if self.risk_manager else {},
            "scanner": self.scanner.scan_stats if self.scanner else {},
        }


# ── Thread-safe singleton ─────────────────────────────────────────────────
_bot_instance: Optional[TradingBot] = None
_bot_lock = threading.Lock()


def get_bot() -> TradingBot:
    """Return the process-wide TradingBot singleton (thread-safe)."""
    global _bot_instance
    if _bot_instance is None:
        with _bot_lock:
            if _bot_instance is None:
                _bot_instance = TradingBot()
    return _bot_instance
