"""
Main trading bot orchestrator.

Runs the full pipeline in a continuous loop:
1. Check filters (session + news)
2. Fetch multi-timeframe data
3. Run strategy analysis
4. Score with AI classifier
5. Validate risk
6. Execute trade
7. Manage open positions
8. Persist to database

Supports paper and live trading modes.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Optional

from ai.classifier import TradeClassifier
from ai.feature_engine import extract_features
from api.routes import set_bot_reference
from config.settings import AppConfig, TradingMode, get_config
from core.logger import get_logger, setup_logger
from core.models import Trade, TradeSignal, TradeStatus
from data.binance_provider import BinanceDataProvider
from data.mt5_provider import MT5DataProvider
from database.repository import TradingRepository
from execution.binance_executor import BinanceExecutor
from execution.mt5_executor import MT5Executor
from execution.paper_executor import PaperExecutor
from filters.news_filter import NewsFilter
from filters.session_filter import SessionFilter
from risk.risk_manager import RiskManager
from strategy.smc_strategy import SMCStrategy
from trade_management.manager import TradeManager

logger = get_logger("bot")

SCAN_INTERVAL_SECONDS = 60
MANAGEMENT_INTERVAL_SECONDS = 15
SNAPSHOT_INTERVAL_SECONDS = 300


class TradingBot:
    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or get_config()
        self.running = False
        self.start_time: Optional[datetime] = None
        self.recent_signals: list[dict] = []

        self.mt5_data = MT5DataProvider(self.config.mt5)
        self.binance_data = BinanceDataProvider(self.config.binance)
        self.strategy = SMCStrategy(self.config.strategy)
        self.risk_manager = RiskManager(self.config.risk)
        self.trade_manager = TradeManager(self.config.strategy)
        self.classifier = TradeClassifier()
        self.session_filter = SessionFilter(self.config.session)
        self.news_filter = NewsFilter(self.config.news)
        self.db = TradingRepository(self.config.database)

        self.mt5_executor = MT5Executor(self.config.mt5)
        self.binance_executor = BinanceExecutor(self.config.binance)
        self.paper_executor = PaperExecutor()

    async def start(self):
        """Initialize all connections and start the main loop."""
        root_logger = setup_logger(level=self.config.log_level)
        logger.info("=" * 60)
        logger.info(f"AI Trading Bot starting — mode={self.config.mode.value}")
        logger.info("=" * 60)

        self.db.connect()

        if self.config.mode == TradingMode.LIVE:
            mt5_ok = await self.mt5_data.connect()
            if mt5_ok:
                logger.info("MT5 connected for live forex trading")
            binance_ok = await self.binance_data.connect()
            if binance_ok:
                logger.info("Binance connected for live crypto trading")
            await self.binance_executor.connect()
        else:
            binance_ok = await self.binance_data.connect()
            if binance_ok:
                logger.info("Binance connected for market data (paper mode)")
            await self.mt5_data.connect()

        await self.news_filter.fetch_events()

        set_bot_reference(self)

        self.running = True
        self.start_time = datetime.utcnow()

        logger.info("Bot initialized — entering main loop")

        await asyncio.gather(
            self._scan_loop(),
            self._management_loop(),
            self._snapshot_loop(),
            self._news_refresh_loop(),
        )

    async def stop(self):
        """Graceful shutdown."""
        logger.info("Shutting down...")
        self.running = False
        await self.mt5_data.disconnect()
        await self.binance_data.disconnect()
        await self.binance_executor.disconnect()
        logger.info("Bot stopped")

    async def _scan_loop(self):
        """Main scanning loop: analyze symbols for trade signals."""
        while self.running:
            try:
                if not self.session_filter.is_active_session():
                    wait = self.session_filter.time_until_next_session()
                    logger.debug(f"Outside trading session — next in {wait}min")
                    await asyncio.sleep(min(wait * 60, 300))
                    continue

                can_trade, reason = self.risk_manager.can_trade()
                if not can_trade:
                    logger.info(f"Risk gate blocked: {reason}")
                    await asyncio.sleep(SCAN_INTERVAL_SECONDS)
                    continue

                if self.config.forex_symbols:
                    await self._scan_market(self.config.forex_symbols, "forex")

                if self.config.crypto_symbols:
                    await self._scan_market(self.config.crypto_symbols, "crypto")

            except Exception as e:
                logger.error(f"Scan loop error: {e}", exc_info=True)

            await asyncio.sleep(SCAN_INTERVAL_SECONDS)

    async def _scan_market(self, symbols: list[str], market: str):
        """Scan a list of symbols for signals."""
        for symbol in symbols:
            try:
                can_trade, reason = self.risk_manager.can_trade()
                if not can_trade:
                    break

                safe, news_reason = self.news_filter.is_safe_to_trade(symbol)
                if not safe:
                    logger.info(f"{symbol}: Blocked by news filter — {news_reason}")
                    continue

                provider = self.mt5_data if market == "forex" else self.binance_data
                h1 = await provider.get_candles(symbol, "H1", 200)
                m15 = await provider.get_candles(symbol, "M15", 200)
                m5 = await provider.get_candles(symbol, "M5", 200)

                if h1.empty or m15.empty or m5.empty:
                    continue

                signal = await self.strategy.analyze(h1, m15, m5, symbol)
                if signal is None:
                    continue

                combined_score, ai_score = self.classifier.score_signal(
                    h1, m15, m5, signal.confidence
                )
                signal.confidence = combined_score
                signal.ai_score = ai_score

                if signal.confidence < self.config.strategy.min_confidence:
                    logger.info(
                        f"{symbol}: Signal rejected — confidence {signal.confidence:.2f} "
                        f"< {self.config.strategy.min_confidence}"
                    )
                    self._record_signal(signal, executed=False,
                                        reject_reason="low_confidence")
                    continue

                valid, risk_reason = self.risk_manager.validate_signal(signal)
                if not valid:
                    logger.info(f"{symbol}: Risk rejected — {risk_reason}")
                    self._record_signal(signal, executed=False,
                                        reject_reason=risk_reason)
                    continue

                symbol_info = None
                if market == "forex":
                    symbol_info = await self.mt5_data.get_symbol_info(symbol)
                position_size = self.risk_manager.calculate_position_size(signal, symbol_info)

                if position_size <= 0:
                    logger.warning(f"{symbol}: Invalid position size")
                    continue

                trade = await self._execute_trade(signal, position_size, market)
                if trade:
                    self.risk_manager.register_trade(trade)
                    self.db.save_trade(trade)
                    self._record_signal(signal, executed=True)

                    features = extract_features(h1, m15, m5)
                    self.db.save_ml_data(trade.trade_id, features, label=-1)

                    logger.info(
                        f"Trade opened: {trade.trade_id} {symbol} "
                        f"{signal.direction.value} size={position_size}"
                    )

            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}", exc_info=True)

    async def _execute_trade(self, signal: TradeSignal, size: float, market: str) -> Optional[Trade]:
        """Route execution to the correct engine."""
        if self.config.mode == TradingMode.PAPER:
            return await self.paper_executor.place_order(signal, size)

        if market == "forex":
            return await self.mt5_executor.place_order(signal, size)
        return await self.binance_executor.place_order(signal, size)

    async def _management_loop(self):
        """Monitor and manage open positions."""
        while self.running:
            try:
                for trade in list(self.risk_manager.open_trades):
                    if trade.status not in (TradeStatus.OPEN, TradeStatus.PARTIAL_CLOSE):
                        continue

                    price_data = await self._get_current_price(trade)
                    if price_data is None:
                        continue

                    current_price = price_data["last"] or price_data["bid"]
                    trade.current_price = current_price

                    actions = self.trade_manager.check_trade(trade, current_price)

                    for action in actions:
                        await self._handle_trade_action(trade, action)

                unrealized = self.trade_manager.get_unrealized_pnl(
                    self.risk_manager.open_trades
                )
                self.risk_manager.update_equity(unrealized)

            except Exception as e:
                logger.error(f"Management loop error: {e}", exc_info=True)

            await asyncio.sleep(MANAGEMENT_INTERVAL_SECONDS)

    async def _handle_trade_action(self, trade: Trade, action: dict):
        """Process trade management actions (TP hits, SL, breakeven)."""
        act = action["action"]

        if act == "close_full":
            pnl = action["pnl"]
            if self.config.mode == TradingMode.PAPER:
                await self.paper_executor.close_position(trade)
            elif trade.market == "forex":
                await self.mt5_executor.close_position(trade)
            else:
                await self.binance_executor.close_position(trade)

            self.risk_manager.close_trade(trade, pnl)
            self.db.update_trade(trade)

            self._update_ml_label(trade)

            logger.info(
                f"Trade closed: {trade.trade_id} reason={action['reason']} pnl={pnl:.2f}"
            )

        elif act == "partial_close":
            size = action["size"]
            if self.config.mode == TradingMode.PAPER:
                await self.paper_executor.close_position(trade, size)
            elif trade.market == "forex":
                await self.mt5_executor.close_position(trade, size)
            else:
                await self.binance_executor.close_position(trade, size)

            trade.partial_closes.append({
                "reason": action["reason"],
                "size": size,
                "price": action["price"],
                "pnl": action["pnl"],
            })
            self.db.update_trade(trade)
            logger.info(
                f"Partial close: {trade.trade_id} {action['reason']} size={size:.4f}"
            )

        elif act == "move_sl":
            new_sl = action["new_sl"]
            trade.stop_loss = new_sl
            if self.config.mode == TradingMode.PAPER:
                await self.paper_executor.modify_sl(trade, new_sl)
            elif trade.market == "forex":
                await self.mt5_executor.modify_sl(trade, new_sl)
            self.db.update_trade(trade)

    async def _get_current_price(self, trade: Trade) -> Optional[dict]:
        if trade.market == "forex":
            return await self.mt5_data.get_current_price(trade.symbol)
        elif trade.market == "crypto":
            return await self.binance_data.get_current_price(trade.symbol)
        elif trade.market == "paper":
            price = await self.binance_data.get_current_price(trade.symbol)
            if price is None:
                price = await self.mt5_data.get_current_price(trade.symbol)
            return price
        return None

    async def _snapshot_loop(self):
        """Periodically save account state to database."""
        while self.running:
            try:
                self.db.save_account_snapshot(self.risk_manager.account)
            except Exception as e:
                logger.error(f"Snapshot error: {e}")
            await asyncio.sleep(SNAPSHOT_INTERVAL_SECONDS)

    async def _news_refresh_loop(self):
        """Periodically refresh news data."""
        while self.running:
            await asyncio.sleep(3600)
            try:
                await self.news_filter.refresh_if_needed()
            except Exception as e:
                logger.error(f"News refresh error: {e}")

    def _record_signal(self, signal: TradeSignal, executed: bool, reject_reason: str = ""):
        record = {
            "signal_id": signal.signal_id,
            "symbol": signal.symbol,
            "direction": signal.direction.value,
            "entry_price": signal.entry_price,
            "confidence": signal.confidence,
            "ai_score": signal.ai_score,
            "executed": executed,
            "reject_reason": reject_reason,
            "timestamp": signal.timestamp.isoformat(),
        }
        self.recent_signals.append(record)
        if len(self.recent_signals) > 100:
            self.recent_signals = self.recent_signals[-100:]
        self.db.save_signal(signal)

    def _update_ml_label(self, trade: Trade):
        """Update ML training label after trade closes."""
        label = 1 if trade.pnl > 0 else 0
        try:
            session = self.db._get_session()
            if session:
                from database.models import MLTrainingData
                record = session.query(MLTrainingData).filter_by(
                    trade_id=trade.trade_id
                ).first()
                if record:
                    record.label = label
                    session.commit()
                session.close()
        except Exception as e:
            logger.error(f"ML label update error: {e}")
