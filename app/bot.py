from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.classifier import TradeClassifier
from app.analysis.multi_timeframe import MTFAnalysis, MultiTimeframeAnalyzer
from app.core.config import Settings, TradingMode, settings
from app.core.database import AsyncSessionLocal
from app.execution.base import ExecutionEngine, OrderResult
from app.execution.binance_executor import BinanceExecutor
from app.execution.mt5_executor import MT5Executor
from app.execution.paper_executor import PaperExecutor
from app.filters.news_filter import NewsFilter
from app.filters.session_filter import SessionFilter
from app.market_data.binance_provider import BinanceDataProvider
from app.market_data.mt5_provider import MT5DataProvider
from app.models.signal import Signal
from app.models.trade import Trade, TradeStatus, TradeSide
from app.risk.manager import RiskManager
from app.strategy.engine import StrategyEngine, TradeSetup
from app.trade_management.manager import TradeAction, TradeManager


class TradingBot:
    """
    Main orchestrator.

    Cycle (every M5 candle close ≈ 5 min):
      1. Refresh news calendar (periodically)
      2. Check session filter
      3. For each symbol → MTF analysis
      4. Strategy evaluation → trade setups
      5. AI confidence gate
      6. Risk check
      7. Execute or reject
      8. Manage open trades (TP/SL/BE)
    """

    def __init__(self) -> None:
        self.settings: Settings = settings
        self.is_running: bool = False
        self._start_time: float = 0.0
        self._cycle_interval: int = 300  # 5 minutes

        # Components
        self.risk_manager = RiskManager()
        self.strategy = StrategyEngine(atr_sl_multiplier=1.5, use_structure_sl=True)
        self.trade_manager = TradeManager()
        self.classifier = TradeClassifier()
        self.news_filter = NewsFilter()
        self.session_filter = SessionFilter()

        # Data providers
        self._mt5_data = MT5DataProvider()
        self._binance_data = BinanceDataProvider()

        # Executors
        self._mt5_executor = MT5Executor()
        self._binance_executor = BinanceExecutor()
        self._paper_executor = PaperExecutor()

        # Multi-timeframe analyzers
        self._mt5_analyzer: Optional[MultiTimeframeAnalyzer] = None
        self._binance_analyzer: Optional[MultiTimeframeAnalyzer] = None

        # Active trades in memory
        self._active_trades: Dict[str, Trade] = {}

        # Background tasks
        self._tasks: list[asyncio.Task] = []

    @property
    def uptime_seconds(self) -> float:
        if self._start_time == 0:
            return 0.0
        return time.time() - self._start_time

    @property
    def is_paper(self) -> bool:
        return self.settings.is_paper

    async def initialize(self) -> None:
        """Connect to all services and load models."""
        logger.info(f"Initializing bot in {self.settings.trading_mode.value} mode")

        self.classifier.load_or_train()

        mt5_ok = await self._mt5_data.connect()
        if mt5_ok:
            self._mt5_analyzer = MultiTimeframeAnalyzer(self._mt5_data)
            logger.info("MT5 data feed ready")

        binance_ok = await self._binance_data.connect()
        if binance_ok:
            self._binance_analyzer = MultiTimeframeAnalyzer(self._binance_data)
            logger.info("Binance data feed ready")

        if not self.is_paper:
            if mt5_ok:
                logger.info("MT5 executor ready for live trading")
            if binance_ok:
                await self._binance_executor.connect()
                logger.info("Binance executor ready for live trading")

        await self.news_filter.refresh()
        logger.info("Bot initialization complete")

    def start(self) -> None:
        """Start the bot loop (non-blocking — call from asyncio context)."""
        if self.is_running:
            return
        self.is_running = True
        self._start_time = time.time()
        self.risk_manager.reset_session()
        self._tasks.append(asyncio.create_task(self._main_loop()))
        self._tasks.append(asyncio.create_task(self._news_refresh_loop()))
        logger.info("Bot started")

    async def stop(self) -> None:
        """Gracefully stop the bot."""
        self.is_running = False
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()

        await self._mt5_data.disconnect()
        await self._binance_data.disconnect()
        logger.info("Bot stopped")

    # ── Main Loop ────────────────────────────────────────────

    async def _main_loop(self) -> None:
        logger.info("Main trading loop started")
        while self.is_running:
            try:
                await self._trading_cycle()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception(f"Error in trading cycle: {exc}")

            await asyncio.sleep(self._cycle_interval)

    async def _news_refresh_loop(self) -> None:
        while self.is_running:
            try:
                await self.news_filter.refresh()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"News refresh error: {exc}")
            await asyncio.sleep(3600)

    async def _trading_cycle(self) -> None:
        """One full trading cycle."""
        logger.info("─── Trading cycle start ───")

        # Manage existing trades first
        await self._manage_open_trades()

        # Scan for new setups on forex symbols
        forex_active, forex_reason = self.session_filter.is_forex_session_active()
        if forex_active and self._mt5_analyzer:
            for symbol in self.settings.forex_symbols:
                await self._scan_symbol(symbol, "forex", self._mt5_analyzer)

        # Scan crypto symbols (24/7)
        if self._binance_analyzer:
            for symbol in self.settings.crypto_symbols:
                await self._scan_symbol(symbol, "crypto", self._binance_analyzer)

        logger.info("─── Trading cycle end ───")

    async def _scan_symbol(
        self,
        symbol: str,
        market: str,
        analyzer: MultiTimeframeAnalyzer,
    ) -> None:
        """Analyse a single symbol and attempt trade entry."""
        try:
            mtf = await analyzer.analyse(symbol)
            if not mtf.is_valid:
                return

            setups = self.strategy.evaluate(mtf)
            if not setups:
                return

            for setup in setups:
                await self._process_setup(setup, market)

        except Exception as exc:
            logger.error(f"Error scanning {symbol}: {exc}")

    async def _process_setup(self, setup: TradeSetup, market: str) -> None:
        """Run a setup through AI gate, risk check, and execution."""

        # AI confidence gate
        take_it, confidence = self.classifier.should_take_trade(setup)
        if not take_it:
            logger.info(
                f"AI rejected {setup.symbol} {setup.direction} "
                f"(confidence={confidence:.2f} < {self.classifier._min_confidence})"
            )
            return

        # News filter
        safe, reason = self.news_filter.is_safe_to_trade(setup.symbol)
        if not safe:
            logger.info(f"News filter blocked {setup.symbol}: {reason}")
            return

        # Risk check
        risk_check = self.risk_manager.check_trade(
            symbol=setup.symbol,
            direction=setup.direction,
            entry_price=setup.entry_price,
            stop_loss=setup.stop_loss,
            market=market,
        )
        if not risk_check.approved:
            logger.info(f"Risk rejected {setup.symbol}: {risk_check.reason}")
            return

        # Execute
        await self._execute_trade(setup, market, confidence, risk_check.position_size, risk_check.risk_amount)

    async def _execute_trade(
        self,
        setup: TradeSetup,
        market: str,
        confidence: float,
        position_size: float,
        risk_amount: float,
    ) -> None:
        """Place the trade and persist to database."""
        executor = self._get_executor(market)

        result: OrderResult = await executor.place_market_order(
            symbol=setup.symbol,
            side=setup.direction,
            quantity=position_size,
            stop_loss=setup.stop_loss,
            take_profit=setup.tp1,
        )

        if not result.success:
            logger.error(f"Order failed for {setup.symbol}: {result.error}")
            return

        filled_price = result.filled_price or setup.entry_price

        # Persist trade
        trade = Trade(
            symbol=setup.symbol,
            market=market,
            side=setup.direction,
            status=TradeStatus.OPEN.value,
            entry_price=filled_price,
            stop_loss=setup.stop_loss,
            original_stop_loss=setup.stop_loss,
            tp1=setup.tp1,
            tp2=setup.tp2,
            tp3=setup.tp3,
            quantity=position_size,
            risk_amount=risk_amount,
            confidence=confidence,
            is_paper=self.is_paper,
            broker_order_id=result.order_id,
            notes=setup.notes,
            opened_at=datetime.now(timezone.utc),
        )

        # Persist signal
        signal = Signal(
            symbol=setup.symbol,
            signal_type="liquidity_sweep",
            direction=setup.direction,
            confidence=confidence,
            entry_price=filled_price,
            stop_loss=setup.stop_loss,
            tp1=setup.tp1,
            tp2=setup.tp2,
            tp3=setup.tp3,
            timeframe="M5",
            bias_tf="H1",
            notes=setup.notes,
        )

        try:
            async with AsyncSessionLocal() as session:
                session.add(signal)
                await session.flush()
                trade.signal_id = signal.id
                session.add(trade)
                await session.commit()
                await session.refresh(trade)
        except Exception as exc:
            logger.error(f"DB persist failed: {exc}")

        self._active_trades[setup.symbol] = trade
        self.risk_manager.register_trade_opened(setup.symbol, setup.direction)

        trade_logger = logger.bind(trade=True)
        trade_logger.info(
            f"TRADE OPENED: {trade.symbol} {trade.side} @ {filled_price:.5f} "
            f"SL={trade.stop_loss:.5f} TP1={trade.tp1:.5f} TP2={trade.tp2:.5f} "
            f"TP3={trade.tp3:.5f} size={position_size} conf={confidence:.2f} "
            f"{'[PAPER]' if self.is_paper else '[LIVE]'}"
        )

    # ── Trade Management ─────────────────────────────────────

    async def _manage_open_trades(self) -> None:
        """Check TP/SL/BE for all active trades."""
        for symbol, trade in list(self._active_trades.items()):
            try:
                price = await self._get_current_price(symbol, trade.market)
                if price == 0:
                    continue

                decisions = self.trade_manager.evaluate(
                    current_price=price,
                    side=trade.side,
                    entry_price=trade.entry_price,
                    stop_loss=trade.stop_loss,
                    tp1=trade.tp1,
                    tp2=trade.tp2,
                    tp3=trade.tp3,
                    tp1_hit=trade.tp1_hit,
                    tp2_hit=trade.tp2_hit,
                    tp3_hit=trade.tp3_hit,
                    break_even_set=trade.break_even_set,
                )

                for decision in decisions:
                    await self._apply_decision(trade, decision, price)

            except Exception as exc:
                logger.error(f"Error managing {symbol}: {exc}")

    async def _apply_decision(self, trade: Trade, decision, price: float) -> None:
        executor = self._get_executor(trade.market)

        if decision.action == TradeAction.STOP_LOSS_HIT:
            await self._close_trade(trade, price, "Stop loss hit")

        elif decision.action == TradeAction.CLOSE_TP3:
            await self._close_trade(trade, price, "TP3 (2R) hit")

        elif decision.action == TradeAction.PARTIAL_CLOSE_TP1:
            close_qty = trade.quantity * decision.close_pct
            await executor.close_position(trade.symbol, trade.side, close_qty, trade.broker_order_id)
            trade.tp1_hit = True
            trade.status = TradeStatus.PARTIALLY_CLOSED.value
            logger.info(f"TP1 partial close: {trade.symbol} qty={close_qty:.6f}")

        elif decision.action == TradeAction.PARTIAL_CLOSE_TP2:
            close_qty = trade.quantity * decision.close_pct
            await executor.close_position(trade.symbol, trade.side, close_qty, trade.broker_order_id)
            trade.tp2_hit = True
            logger.info(f"TP2 partial close: {trade.symbol} qty={close_qty:.6f}")

        elif decision.action == TradeAction.MOVE_TO_BREAKEVEN:
            if decision.new_stop_loss is not None:
                await executor.modify_stop_loss(
                    trade.symbol, trade.broker_order_id or "", decision.new_stop_loss
                )
                trade.stop_loss = decision.new_stop_loss
                trade.break_even_set = True
                logger.info(f"Break-even set: {trade.symbol} SL → {decision.new_stop_loss:.5f}")

        # Persist changes
        try:
            async with AsyncSessionLocal() as session:
                merged = await session.merge(trade)
                await session.commit()
        except Exception as exc:
            logger.error(f"Failed to update trade: {exc}")

    async def _close_trade(self, trade: Trade, price: float, reason: str) -> None:
        executor = self._get_executor(trade.market)
        remaining_qty = trade.quantity
        if trade.tp1_hit:
            remaining_qty *= (1.0 - 0.33)
        if trade.tp2_hit:
            remaining_qty *= (1.0 - 0.33)

        await executor.close_position(trade.symbol, trade.side, remaining_qty, trade.broker_order_id)

        if trade.side == "long":
            pnl = (price - trade.entry_price) * trade.quantity
        else:
            pnl = (trade.entry_price - price) * trade.quantity

        trade.exit_price = price
        trade.pnl = pnl
        trade.pnl_pct = (pnl / trade.risk_amount * 100) if trade.risk_amount else 0
        trade.status = TradeStatus.CLOSED.value
        trade.closed_at = datetime.now(timezone.utc)

        if isinstance(executor, PaperExecutor):
            executor.update_balance(pnl)

        self.risk_manager.register_trade_closed(trade.symbol, pnl)
        self._active_trades.pop(trade.symbol, None)

        try:
            async with AsyncSessionLocal() as session:
                await session.merge(trade)
                await session.commit()
        except Exception as exc:
            logger.error(f"Failed to close trade in DB: {exc}")

        trade_logger = logger.bind(trade=True)
        trade_logger.info(
            f"TRADE CLOSED: {trade.symbol} {trade.side} @ {price:.5f} "
            f"PnL=${pnl:.2f} ({trade.pnl_pct:.1f}%) reason={reason} "
            f"{'[PAPER]' if trade.is_paper else '[LIVE]'}"
        )

    # ── Helpers ──────────────────────────────────────────────

    def _get_executor(self, market: str) -> ExecutionEngine:
        if self.is_paper:
            return self._paper_executor
        if market == "forex":
            return self._mt5_executor
        return self._binance_executor

    async def _get_current_price(self, symbol: str, market: str) -> float:
        if market == "forex":
            return await self._mt5_data.get_current_price(symbol)
        return await self._binance_data.get_current_price(symbol)
