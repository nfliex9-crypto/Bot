from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from app.ai.model import RandomForestConfidenceModel
from app.core.config import Settings
from app.domain.models import MarketType, OpenTrade, TradeSide, TradingMode, default_symbol_specs
from app.execution.binance import BinanceBroker
from app.execution.mt5 import MT5Broker
from app.execution.paper import PaperBroker
from app.filters.news import HighImpactNewsFilter
from app.filters.session import SessionFilter
from app.marketdata.providers import BinanceMarketDataProvider, MT5MarketDataProvider
from app.risk.manager import RiskManager
from app.services.repository import TradingRepository
from app.strategy.liquidity import LiquiditySweepStrategy

logger = logging.getLogger(__name__)


class TradingEngine:
    def __init__(self, settings: Settings, repository: TradingRepository):
        self.settings = settings
        self.repository = repository
        self.strategy = LiquiditySweepStrategy(settings)
        self.model = RandomForestConfidenceModel(settings.model_path)
        self.risk = RiskManager(settings)
        self.session_filter = SessionFilter()
        self.news_filter = HighImpactNewsFilter(settings)
        self.symbol_specs = default_symbol_specs()

        self.paper_broker = PaperBroker(settings)
        self._binance_broker: BinanceBroker | None = None
        self._mt5_broker: MT5Broker | None = None
        self._binance_data: BinanceMarketDataProvider | None = None
        self._mt5_data: MT5MarketDataProvider | None = None

        self._runner_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._last_news_sync: datetime | None = None

    async def start_background(self) -> None:
        if self._runner_task and not self._runner_task.done():
            return
        self._stop_event.clear()
        self._runner_task = asyncio.create_task(self.run_forever(), name="trading-engine")

    async def shutdown(self) -> None:
        self._stop_event.set()
        if self._runner_task:
            await self._runner_task

    async def run_forever(self) -> None:
        while not self._stop_event.is_set():
            error: str | None = None
            try:
                await self._run_cycle()
            except Exception as exc:  # pragma: no cover - safety net
                logger.exception("Engine cycle failed")
                error = str(exc)
            finally:
                self.repository.touch_heartbeat(error=error)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.settings.loop_interval_seconds)
            except TimeoutError:
                continue

    async def _run_cycle(self) -> None:
        state = self.repository.get_bot_state()
        if not state.enabled:
            return

        mode = TradingMode(state.mode)
        await self._maybe_sync_news()
        events = self.repository.list_events()
        await self._manage_open_trades(mode)

        if not self.session_filter.is_session_open():
            return

        universe = [(MarketType.FOREX, symbol) for symbol in self.settings.symbols_forex] + [
            (MarketType.CRYPTO, symbol) for symbol in self.settings.symbols_crypto
        ]
        for market, symbol in universe:
            try:
                await self._scan_symbol(mode, market, symbol, events)
            except Exception:
                logger.exception("Symbol scan failed for %s", symbol)

    async def _scan_symbol(self, mode: TradingMode, market: MarketType, symbol: str, events) -> None:
        if self.repository.count_open_trades_for_symbol(symbol) > 0:
            return
        if symbol not in self.symbol_specs:
            logger.warning("No symbol specification for %s", symbol)
            return

        spec = self.symbol_specs[symbol]
        if self.news_filter.blocks_trade(events, [spec.base_currency, spec.quote_currency]):
            return

        h1 = await self._data_provider(market).fetch_candles(symbol, "H1", self.settings.h1_lookback)
        m15 = await self._data_provider(market).fetch_candles(symbol, "M15", self.settings.m15_lookback)
        m5 = await self._data_provider(market).fetch_candles(symbol, "M5", self.settings.m5_lookback)

        signal = self.strategy.generate_signal(symbol, market, h1, m15, m5)
        if signal is None:
            return

        signal.metadata["feature_map"]["session_score"] = self.session_filter.session_score()
        signal.metadata["feature_map"]["news_risk"] = self.news_filter.news_risk_score(
            events,
            [spec.base_currency, spec.quote_currency],
        )
        score = self.model.score(signal.metadata["feature_map"], fallback=signal.confidence)
        signal.confidence = score.confidence
        signal.metadata["ai_source"] = score.source
        if signal.confidence < self.settings.min_confidence:
            return

        account = await self._account_snapshot(mode, market)
        risk_decision = self.risk.can_open_trade(account)
        if not risk_decision.allowed:
            logger.info("Trade blocked for %s: %s", symbol, risk_decision.reason)
            return

        sized_signal = self.risk.size_trade(signal, account, spec)
        broker = self._broker(mode, market)
        order_result = await broker.place_trade(sized_signal)
        self.repository.create_trade(sized_signal, mode, order_result)
        logger.info("Placed %s %s on %s with confidence %.2f", signal.side.value, symbol, market.value, signal.confidence)

    async def _manage_open_trades(self, mode: TradingMode) -> None:
        for trade in self.repository.list_open_trades():
            try:
                await self._manage_trade(mode, trade)
            except Exception:
                logger.exception("Open trade management failed for %s", trade.trade_id)

    async def _manage_trade(self, mode: TradingMode, trade: OpenTrade) -> None:
        broker = self._broker(mode, trade.market)
        current_price = await self._data_provider(trade.market).fetch_last_price(trade.symbol)
        spec = self.symbol_specs.get(trade.symbol)
        if spec is None:
            return

        tp_size = round(trade.position_size / 3, spec.qty_precision)
        if trade.side == TradeSide.BUY:
            stop_hit = current_price <= trade.stop_loss
            tp1_hit = current_price >= trade.take_profit_1
            tp2_hit = current_price >= trade.take_profit_2
            tp3_hit = current_price >= trade.take_profit_3
        else:
            stop_hit = current_price >= trade.stop_loss
            tp1_hit = current_price <= trade.take_profit_1
            tp2_hit = current_price <= trade.take_profit_2
            tp3_hit = current_price <= trade.take_profit_3

        if stop_hit:
            await broker.close_trade(trade, "stop_loss")
            pnl = self._pnl(trade.entry_price, trade.stop_loss, trade.remaining_size, trade.side, spec)
            self.repository.close_trade(trade.trade_id, 0.0, pnl, "stop_loss")
            await broker.book_realized_pnl(trade.market, pnl)
            return

        if tp1_hit and not trade.tp1_hit:
            qty = min(tp_size, trade.remaining_size)
            await broker.close_partial(trade, qty, "tp1")
            pnl = self._pnl(trade.entry_price, trade.take_profit_1, qty, trade.side, spec)
            trade = self.repository.mark_tp(trade.trade_id, 1, max(trade.remaining_size - qty, 0.0), pnl)
            trade.stop_loss = trade.entry_price
            self.repository.update_stop(trade.trade_id, trade.entry_price, True)
            await broker.move_stop_to_break_even(trade)
            await broker.book_realized_pnl(trade.market, pnl)

        if tp2_hit and not trade.tp2_hit and trade.remaining_size > 0:
            qty = min(tp_size, trade.remaining_size)
            await broker.close_partial(trade, qty, "tp2")
            pnl = self._pnl(trade.entry_price, trade.take_profit_2, qty, trade.side, spec)
            trade = self.repository.mark_tp(trade.trade_id, 2, max(trade.remaining_size - qty, 0.0), pnl)
            await broker.book_realized_pnl(trade.market, pnl)

        if tp3_hit and trade.remaining_size > 0:
            qty = trade.remaining_size
            await broker.close_partial(trade, qty, "tp3")
            pnl = self._pnl(trade.entry_price, trade.take_profit_3, qty, trade.side, spec)
            self.repository.mark_tp(trade.trade_id, 3, 0.0, pnl)
            await broker.book_realized_pnl(trade.market, pnl)

    async def _maybe_sync_news(self) -> None:
        if not self.settings.news_sync_url:
            return
        if self._last_news_sync and datetime.now(UTC) - self._last_news_sync < timedelta(minutes=15):
            return
        events = await self.news_filter.sync_events()
        self.repository.replace_events(events)
        self._last_news_sync = datetime.now(UTC)

    async def _account_snapshot(self, mode: TradingMode, market: MarketType):
        snapshot = await self._broker(mode, market).get_account_snapshot(market)
        if mode == TradingMode.LIVE:
            snapshot.session_trade_count = self.repository.count_session_trades(market)
        return snapshot

    def _broker(self, mode: TradingMode, market: MarketType):
        if mode == TradingMode.PAPER:
            return self.paper_broker
        if market == MarketType.CRYPTO:
            if self._binance_broker is None:
                self._binance_broker = BinanceBroker(self.settings)
            return self._binance_broker
        if self._mt5_broker is None:
            self._mt5_broker = MT5Broker(self.settings)
        return self._mt5_broker

    def _data_provider(self, market: MarketType):
        if market == MarketType.CRYPTO:
            if self._binance_data is None:
                self._binance_data = BinanceMarketDataProvider(self.settings)
            return self._binance_data
        if self._mt5_data is None:
            self._mt5_data = MT5MarketDataProvider(self.settings)
        return self._mt5_data

    def status(self) -> dict[str, object]:
        state = self.repository.get_bot_state()
        return {
            "enabled": state.enabled,
            "mode": state.mode,
            "heartbeat_at": state.heartbeat_at.isoformat() if state.heartbeat_at else None,
            "last_error": state.last_error,
            "open_trades": len(self.repository.list_open_trades()),
            "model_trained": self.model.is_trained(),
        }

    @staticmethod
    def _pnl(entry: float, exit_price: float, quantity: float, side: TradeSide, spec) -> float:
        move = exit_price - entry if side == TradeSide.BUY else entry - exit_price
        ticks = move / max(spec.tick_size, 1e-12)
        return ticks * spec.tick_value * quantity
