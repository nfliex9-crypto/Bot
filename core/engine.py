from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional

from config.settings import settings
from core.data_feed import DataFeed
from core.models import (
    AccountState,
    Direction,
    Market,
    OpenTrade,
    Session,
    TradeSignal,
    TradeStatus,
)
from ai.classifier import classifier_registry
from database.connection import get_db_session
from database.models import AccountSnapshot, SignalLog, TradeRecord
from execution.base_executor import BaseExecutor
from execution.binance_executor import BinanceExecutor
from execution.mt5_executor import MT5Executor
from filters.news_filter import news_filter
from filters.session_filter import session_filter
from risk.risk_manager import risk_manager
from strategy.analyzer import MultiTimeframeAnalyzer
from utils.helpers import generate_trade_id, serialize_signals
from utils.logger import get_logger

logger = get_logger(__name__)


class TradingEngine:
    """
    The central orchestrator for the AI trading bot.

    Responsibilities:
    - Initialise and manage market connections
    - Drive the main trading loop for each market
    - Coordinate MTF analysis → AI scoring → risk checks → order execution
    - Manage trade lifecycle (partial closes, break-even, full close)
    - Persist all activity to the database
    - Expose engine state to the API layer
    """

    def __init__(self) -> None:
        self._mt5: MT5Executor = MT5Executor()
        self._binance: BinanceExecutor = BinanceExecutor()
        self._forex_feed: DataFeed = DataFeed(self._mt5)
        self._crypto_feed: DataFeed = DataFeed(self._binance)
        self._analyzer: MultiTimeframeAnalyzer = MultiTimeframeAnalyzer()

        self._account = AccountState(
            balance=settings.account_balance,
            equity=settings.account_balance,
            peak_equity=settings.account_balance,
        )
        self._running = False
        self._paused = False
        self._cycle_count = 0
        self._errors: List[str] = []

    # ──────────────────────────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────────────────────────

    async def start(self) -> None:
        logger.info(
            "Starting AI Trading Engine | mode=%s", settings.trading_mode.upper()
        )
        forex_ok = await self._mt5.connect()
        crypto_ok = await self._binance.connect()

        if not forex_ok:
            logger.warning("MT5 connection failed — Forex disabled for this session")
        if not crypto_ok:
            logger.warning("Binance connection failed — Crypto disabled for this session")

        # Initial news refresh
        await news_filter.refresh()

        # Load initial historical data
        timeframes = [settings.bias_timeframe, settings.trend_timeframe, settings.entry_timeframe]
        if forex_ok:
            await self._forex_feed.initialise(settings.forex_symbol_list, timeframes)
        if crypto_ok:
            await self._crypto_feed.initialise(settings.crypto_symbol_list, timeframes)

        self._running = True
        logger.info("Trading engine ready. Starting main loop...")
        await self._main_loop()

    async def stop(self) -> None:
        logger.info("Stopping trading engine...")
        self._running = False
        await self._mt5.disconnect()
        await self._binance.disconnect()

    def pause(self) -> None:
        self._paused = True
        logger.info("Trading engine PAUSED")

    def resume(self) -> None:
        self._paused = False
        logger.info("Trading engine RESUMED")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    # ──────────────────────────────────────────────────────────────────
    # Main loop
    # ──────────────────────────────────────────────────────────────────

    async def _main_loop(self) -> None:
        """
        Master trading loop. Runs continuously while self._running.
        Each cycle:
          1. Refresh news
          2. Update account state
          3. Manage open trades (TP, SL, break-even)
          4. Scan for new signals
          5. Sleep until next bar
        """
        while self._running:
            try:
                if not self._paused:
                    self._cycle_count += 1
                    await self._cycle()
            except Exception as exc:
                err_msg = f"Engine cycle error: {exc}"
                logger.exception(err_msg)
                self._errors.append(
                    f"[{datetime.now(timezone.utc).isoformat()}] {err_msg}"
                )
                self._errors = self._errors[-50:]   # keep last 50

            await asyncio.sleep(60)   # M5 bars = ~60s scan interval

    async def _cycle(self) -> None:
        # Refresh external data (news, session)
        if self._cycle_count % 60 == 0:   # every hour
            await news_filter.refresh()

        # Reset session trade counter at start of new trading session
        self._reset_session_counter_if_needed()

        # Update account snapshot
        await self._update_account()

        # Manage existing open trades
        await self._manage_open_trades()

        # Scan for new signals — only during active sessions
        current_session = session_filter.current_session()
        if current_session in (Session.LONDON, Session.NEW_YORK, Session.LONDON_NY_OVERLAP):
            await self._scan_signals(Market.FOREX, settings.forex_symbol_list, self._forex_feed, self._mt5)
            await self._scan_signals(Market.CRYPTO, settings.crypto_symbol_list, self._crypto_feed, self._binance)

        # Persist account snapshot every 5 cycles
        if self._cycle_count % 5 == 0:
            await self._save_account_snapshot()

    # ──────────────────────────────────────────────────────────────────
    # Signal scanning
    # ──────────────────────────────────────────────────────────────────

    async def _scan_signals(
        self,
        market: Market,
        symbols: List[str],
        feed: DataFeed,
        executor: BaseExecutor,
    ) -> None:
        for symbol in symbols:
            try:
                await self._process_symbol(symbol, market, feed, executor)
            except Exception as exc:
                logger.warning("Error processing %s: %s", symbol, exc)

    async def _process_symbol(
        self,
        symbol: str,
        market: Market,
        feed: DataFeed,
        executor: BaseExecutor,
    ) -> None:
        # Refresh latest bars
        for tf in [settings.bias_timeframe, settings.trend_timeframe, settings.entry_timeframe]:
            await feed.refresh(symbol, tf)

        h1_df = await feed.get(symbol, settings.bias_timeframe)
        m15_df = await feed.get(symbol, settings.trend_timeframe)
        m5_df = await feed.get(symbol, settings.entry_timeframe)

        if h1_df.empty or m15_df.empty or m5_df.empty:
            return

        # ── News filter ───────────────────────────────────────────────
        if news_filter.is_news_window(symbol):
            logger.debug("Skipping %s — news window active", symbol)
            return

        # ── Session filter ────────────────────────────────────────────
        if not session_filter.is_tradeable(symbol):
            return

        # ── Multi-timeframe analysis ──────────────────────────────────
        mta = self._analyzer.analyse(symbol, h1_df, m15_df, m5_df)
        if not mta.aligned:
            return

        direction = self._analyzer.get_trade_direction(mta)
        if direction is None:
            return

        # ── Session context ───────────────────────────────────────────
        current_session = session_filter.current_session()
        session_flags = {
            "london": current_session in (Session.LONDON, Session.LONDON_NY_OVERLAP),
            "new_york": current_session in (Session.NEW_YORK, Session.LONDON_NY_OVERLAP),
            "overlap": current_session == Session.LONDON_NY_OVERLAP,
        }

        # ── AI confidence scoring ─────────────────────────────────────
        confidence = classifier_registry.predict(symbol, m5_df, mta, session_flags)
        if confidence < settings.ai_confidence_threshold:
            logger.debug(
                "Skipping %s — confidence %.3f < threshold %.3f",
                symbol, confidence, settings.ai_confidence_threshold,
            )
            await self._log_signal(symbol, market, mta, direction, confidence, executed=False, reason="low_confidence")
            return

        # ── Risk validation ───────────────────────────────────────────
        risk_result = risk_manager.validate_trade(
            symbol, market, direction, m5_df, self._account, mta
        )
        if not risk_result.allowed:
            logger.info("Trade REJECTED for %s: %s", symbol, risk_result.reason)
            await self._log_signal(symbol, market, mta, direction, confidence, executed=False, reason=risk_result.reason)
            return

        # ── Build TradeSignal ─────────────────────────────────────────
        entry_price = float(m5_df["close"].iloc[-1])
        trade_id = generate_trade_id(symbol, direction.value)

        signal = TradeSignal(
            symbol=symbol,
            market=market,
            direction=direction,
            entry_price=entry_price,
            stop_loss=risk_result.stop_loss,
            tp1=risk_result.tp1,
            tp2=risk_result.tp2,
            tp3=risk_result.tp3,
            lot_size=risk_result.lot_size,
            risk_amount=risk_result.risk_amount,
            risk_reward=risk_result.risk_reward,
            atr_value=risk_result.atr_value,
            ai_confidence=confidence,
            session=current_session,
            mtf_analysis=mta,
            timestamp=datetime.now(timezone.utc),
            trade_id=trade_id,
            signal_type=f"sweep_bos_pullback_{direction.value}",
            strategy_signals={
                "h1_bias": mta.h1_bias.value,
                "m15_structure": mta.m15_structure.value,
                "sweep": mta.sweep_signal.strength if mta.sweep_signal else 0,
                "bos_direction": mta.bos_signal.direction.value if mta.bos_signal else None,
                "pullback_fib": mta.pullback_signal.fib_level if mta.pullback_signal else None,
            },
        )

        # ── Execute order ─────────────────────────────────────────────
        order_id = await executor.place_order(signal)
        if order_id is None:
            logger.error("Order placement failed for %s", symbol)
            return

        # ── Persist to DB ─────────────────────────────────────────────
        await self._save_trade_record(signal, order_id)
        await self._log_signal(symbol, market, mta, direction, confidence, executed=True)

        # ── Update account state ──────────────────────────────────────
        self._account.session_trades += 1
        open_trade = OpenTrade(
            trade_id=trade_id,
            symbol=symbol,
            market=market,
            direction=direction,
            entry_price=entry_price,
            current_price=entry_price,
            stop_loss=risk_result.stop_loss,
            tp1=risk_result.tp1,
            tp2=risk_result.tp2,
            tp3=risk_result.tp3,
            lot_size=risk_result.lot_size,
            risk_amount=risk_result.risk_amount,
            opened_at=datetime.now(timezone.utc),
            broker_order_id=order_id,
        )
        self._account.open_trades.append(open_trade)

        logger.info(
            "ORDER PLACED | %s %s %s | entry=%.5f SL=%.5f TP1=%.5f | lot=%.4f confidence=%.3f",
            market.value.upper(),
            direction.value.upper(),
            symbol,
            entry_price,
            risk_result.stop_loss,
            risk_result.tp1,
            risk_result.lot_size,
            confidence,
        )

    # ──────────────────────────────────────────────────────────────────
    # Trade management
    # ──────────────────────────────────────────────────────────────────

    async def _manage_open_trades(self) -> None:
        """Check all open trades for TP hits, SL hits, and break-even."""
        for trade in list(self._account.open_trades):
            if trade.status != TradeStatus.OPEN:
                continue
            try:
                await self._update_trade(trade)
            except Exception as exc:
                logger.warning("Error managing trade %s: %s", trade.trade_id, exc)

    async def _update_trade(self, trade: OpenTrade) -> None:
        executor = self._mt5 if trade.market == Market.FOREX else self._binance
        bid, ask = await executor.get_current_price(trade.symbol)
        current_price = bid if trade.direction == Direction.LONG else ask

        if current_price <= 0:
            return

        trade.update_pnl(current_price)

        # ── Stop loss hit ─────────────────────────────────────────────
        if risk_manager.is_stopped_out(trade, current_price):
            await self._close_trade_full(trade, executor, reason="stop_loss", exit_price=current_price)
            return

        # ── Check TPs ─────────────────────────────────────────────────
        tp1_hit, tp2_hit, tp3_hit = risk_manager.check_tp_levels(trade, current_price)

        if tp3_hit and not trade.tp3_hit:
            await self._close_trade_full(trade, executor, reason="tp3", exit_price=current_price)
            return

        if tp2_hit and not trade.tp2_hit:
            trade.tp2_hit = True
            close_pct = settings.tp2_size_pct / (1 - settings.tp1_size_pct)
            await executor.close_partial(trade, close_pct)
            trade.lot_size = round(trade.lot_size * (1 - close_pct), 4)
            await self._update_trade_db(trade.trade_id, {"tp2_hit": True})
            logger.info("TP2 hit on %s at %.5f", trade.symbol, current_price)

        if tp1_hit and not trade.tp1_hit:
            trade.tp1_hit = True
            await executor.close_partial(trade, settings.tp1_size_pct)
            trade.lot_size = round(trade.lot_size * (1 - settings.tp1_size_pct), 4)
            await self._update_trade_db(trade.trade_id, {"tp1_hit": True})
            logger.info("TP1 hit on %s at %.5f", trade.symbol, current_price)

        # ── Break-even ────────────────────────────────────────────────
        if trade.tp1_hit and not trade.breakeven_moved:
            await executor.modify_stop_loss(trade, trade.entry_price)
            trade.stop_loss = trade.entry_price
            trade.breakeven_moved = True
            await self._update_trade_db(trade.trade_id, {"breakeven_moved": True})
            logger.info("Break-even set on %s", trade.symbol)

    # ──────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────

    async def _close_trade_full(
        self,
        trade: OpenTrade,
        executor: BaseExecutor,
        reason: str,
        exit_price: float,
    ) -> None:
        success = await executor.close_trade(trade)
        if success:
            trade.status = TradeStatus.CLOSED
            pnl = self._calculate_pnl(trade, exit_price)
            self._account.balance += pnl
            self._account.open_trades = [
                t for t in self._account.open_trades if t.trade_id != trade.trade_id
            ]
            await self._update_trade_db(
                trade.trade_id,
                {
                    "status": "closed",
                    "exit_price": exit_price,
                    "pnl": pnl,
                    "exit_reason": reason,
                    "closed_at": datetime.now(timezone.utc),
                },
            )
            logger.info(
                "Trade CLOSED | %s %s | reason=%s | exit=%.5f PnL=%.2f",
                trade.symbol, trade.direction.value, reason, exit_price, pnl,
            )

    @staticmethod
    def _calculate_pnl(trade: OpenTrade, exit_price: float) -> float:
        if trade.direction == Direction.LONG:
            diff = exit_price - trade.entry_price
        else:
            diff = trade.entry_price - exit_price
        # Approximate P&L: lot_size * 100000 (forex standard) or qty (crypto)
        if trade.market == Market.FOREX:
            return diff * trade.lot_size * 100_000
        return diff * trade.lot_size

    async def _update_account(self) -> None:
        try:
            forex_bal = await self._mt5.get_account_balance()
            crypto_bal = await self._binance.get_account_balance()
            # Use the combined balance for risk calculations
            self._account.balance = forex_bal + crypto_bal
            self._account.equity = await self._mt5.get_account_equity() + crypto_bal
            self._account.update_drawdown()
        except Exception as exc:
            logger.warning("Account update failed: %s", exc)

    def _reset_session_counter_if_needed(self) -> None:
        now = datetime.now(timezone.utc)
        # Reset counter at the start of each London session (07:00 UTC)
        if now.hour == 7 and now.minute < 2:
            self._account.session_trades = 0

    # ──────────────────────────────────────────────────────────────────
    # Database persistence
    # ──────────────────────────────────────────────────────────────────

    async def _save_trade_record(self, signal: TradeSignal, order_id: str) -> None:
        try:
            async with get_db_session() as session:
                record = TradeRecord(
                    trade_id=signal.trade_id,
                    symbol=signal.symbol,
                    market=signal.market.value,
                    direction=signal.direction.value,
                    mode=settings.trading_mode,
                    entry_price=signal.entry_price,
                    stop_loss=signal.stop_loss,
                    tp1=signal.tp1,
                    tp2=signal.tp2,
                    tp3=signal.tp3,
                    lot_size=signal.lot_size,
                    risk_amount=signal.risk_amount,
                    risk_reward=signal.risk_reward,
                    atr_value=signal.atr_value,
                    ai_confidence=signal.ai_confidence,
                    strategy_signals=serialize_signals(signal.strategy_signals),
                    session=signal.session.value,
                    broker_order_id=order_id,
                )
                session.add(record)
        except Exception as exc:
            logger.error("Failed to save trade record: %s", exc)

    async def _update_trade_db(self, trade_id: str, updates: dict) -> None:
        try:
            from sqlalchemy import select, update
            async with get_db_session() as session:
                await session.execute(
                    update(TradeRecord)
                    .where(TradeRecord.trade_id == trade_id)
                    .values(**updates)
                )
        except Exception as exc:
            logger.error("Failed to update trade DB: %s", exc)

    async def _save_account_snapshot(self) -> None:
        try:
            async with get_db_session() as session:
                snap = AccountSnapshot(
                    balance=self._account.balance,
                    equity=self._account.equity,
                    open_pnl=self._account.open_pnl,
                    daily_pnl=self._account.daily_pnl,
                    drawdown_pct=self._account.drawdown_pct,
                    open_trades=len(self._account.open_trades),
                    mode=settings.trading_mode,
                )
                session.add(snap)
        except Exception as exc:
            logger.error("Failed to save account snapshot: %s", exc)

    async def _log_signal(
        self,
        symbol: str,
        market: Market,
        mta,
        direction: Direction,
        confidence: float,
        executed: bool,
        reason: Optional[str] = None,
    ) -> None:
        try:
            async with get_db_session() as session:
                log = SignalLog(
                    symbol=symbol,
                    market=market.value,
                    direction=direction.value,
                    timeframe=settings.entry_timeframe,
                    signal_type=f"sweep_bos_pullback_{direction.value}",
                    h1_bias=mta.h1_bias.value,
                    m15_structure=mta.m15_structure.value,
                    bos_confirmed=mta.bos_signal is not None and mta.bos_signal.confirmed,
                    sweep_confirmed=mta.sweep_signal is not None and mta.sweep_signal.confirmed,
                    pullback_valid=mta.pullback_signal is not None and mta.pullback_signal.valid,
                    ai_confidence=confidence,
                    executed=executed,
                    rejected_reason=reason,
                )
                session.add(log)
        except Exception as exc:
            logger.error("Failed to log signal: %s", exc)

    # ──────────────────────────────────────────────────────────────────
    # State accessors (for API layer)
    # ──────────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "paused": self._paused,
            "mode": settings.trading_mode,
            "cycle": self._cycle_count,
            "session": session_filter.current_session().value,
            "account": {
                "balance": round(self._account.balance, 2),
                "equity": round(self._account.equity, 2),
                "drawdown_pct": round(self._account.drawdown_pct * 100, 2),
                "session_trades": self._account.session_trades,
                "open_trades": len(self._account.open_trades),
            },
            "errors": self._errors[-10:],
        }

    def get_open_trades(self) -> list:
        return [
            {
                "trade_id": t.trade_id,
                "symbol": t.symbol,
                "market": t.market.value,
                "direction": t.direction.value,
                "entry_price": t.entry_price,
                "current_price": t.current_price,
                "stop_loss": t.stop_loss,
                "tp1": t.tp1,
                "tp2": t.tp2,
                "tp3": t.tp3,
                "lot_size": t.lot_size,
                "unrealised_pnl": round(t.unrealised_pnl, 2),
                "tp1_hit": t.tp1_hit,
                "tp2_hit": t.tp2_hit,
                "breakeven_moved": t.breakeven_moved,
                "opened_at": t.opened_at.isoformat(),
            }
            for t in self._account.open_trades
        ]
