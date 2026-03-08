from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timezone

from sqlalchemy import func, select

from .ai import TradeConfidenceModel
from .config import Settings, TradingMode
from .data import BinanceDataFeed, MT5DataFeed
from .database import Database
from .domain import MarketType
from .execution import (
    BinanceFuturesExecutionAdapter,
    MT5ExecutionAdapter,
    PaperExecutionAdapter,
)
from .filters import HighImpactNewsFilter, SessionFilter
from .models import Base, BotStateRecord, SignalRecord, TradeRecord
from .news import NewsProvider
from .risk import RiskManager
from .strategy import detect_execution_setup

logger = logging.getLogger(__name__)


class TradingBotService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.database = Database(settings.database_url)
        self.risk_manager = RiskManager(settings)
        self.news_provider = NewsProvider(settings)
        self.session_filter = SessionFilter(settings)
        self.news_filter = HighImpactNewsFilter(settings)
        self.ai_model = TradeConfidenceModel(settings.model_store_path)
        self._task: asyncio.Task | None = None
        self._running = False
        self.data_feeds = self._build_data_feeds()
        self.execution_adapters = self._build_execution_adapters()

    def _build_data_feeds(self) -> dict[MarketType, object]:
        feeds: dict[MarketType, object] = {}
        try:
            feeds[MarketType.CRYPTO] = BinanceDataFeed(
                api_key=self.settings.binance_api_key,
                api_secret=self.settings.binance_api_secret,
                testnet=self.settings.binance_testnet,
            )
        except Exception as exc:
            logger.warning("Binance data feed unavailable: %s", exc)

        try:
            feeds[MarketType.FOREX] = MT5DataFeed(
                login=self.settings.mt5_login,
                password=self.settings.mt5_password,
                server=self.settings.mt5_server,
                path=self.settings.mt5_path,
            )
        except Exception as exc:
            logger.warning("MT5 data feed unavailable: %s", exc)
        return feeds

    def _build_execution_adapters(self) -> dict[MarketType, object]:
        if self.settings.mode == TradingMode.PAPER:
            return {
                MarketType.CRYPTO: PaperExecutionAdapter(MarketType.CRYPTO),
                MarketType.FOREX: PaperExecutionAdapter(MarketType.FOREX),
            }

        adapters: dict[MarketType, object] = {}
        try:
            adapters[MarketType.CRYPTO] = BinanceFuturesExecutionAdapter(
                api_key=self.settings.binance_api_key,
                api_secret=self.settings.binance_api_secret,
                testnet=self.settings.binance_testnet,
            )
        except Exception as exc:
            logger.warning("Binance execution unavailable: %s", exc)
        try:
            adapters[MarketType.FOREX] = MT5ExecutionAdapter()
        except Exception as exc:
            logger.warning("MT5 execution unavailable: %s", exc)
        return adapters

    async def initialize(self) -> None:
        Base.metadata.create_all(self.database.engine)
        with self.database.session() as session:
            self._ensure_state(session)
            closed_records = session.scalars(
                select(TradeRecord).where(TradeRecord.status == "closed")
            ).all()
            self.ai_model.fit_from_records(list(closed_records))
        if self.settings.bot_enabled:
            await self.start()

    async def shutdown(self) -> None:
        await self.stop()

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        with self.database.session() as session:
            state = self._ensure_state(session)
            state.running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        with self.database.session() as session:
            state = self._ensure_state(session)
            state.running = False

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await self.run_once()
            except Exception:
                logger.exception("Trading loop cycle failed")
            await asyncio.sleep(self.settings.cycle_interval_seconds)

    def _ensure_state(self, session) -> BotStateRecord:
        state = session.scalar(select(BotStateRecord).limit(1))
        if state:
            return state
        state = BotStateRecord(
            running=False,
            mode=self.settings.mode.value,
            active_session=None,
            last_cycle_at=None,
            daily_drawdown=0.0,
            open_positions=0,
        )
        session.add(state)
        session.flush()
        return state

    def _session_trade_count(self, session, session_name: str, now: datetime) -> int:
        day_start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
        count = session.scalar(
            select(func.count(TradeRecord.id))
            .where(TradeRecord.session == session_name)
            .where(TradeRecord.opened_at >= day_start)
        )
        return int(count or 0)

    def _todays_realized_pnls(self, session, now: datetime) -> list[float]:
        day_start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
        records = session.scalars(
            select(TradeRecord).where(TradeRecord.opened_at >= day_start)
        ).all()
        return [float(record.realized_pnl) for record in records]

    async def run_once(self) -> dict[str, int]:
        now = datetime.now(timezone.utc)
        evaluated_symbols = 0
        opened_trades = 0
        blocked_by_filters = 0

        with self.database.session() as session:
            state = self._ensure_state(session)
            active_session = self.session_filter.active_session(now)
            self._manage_open_positions(session)

            state.active_session = active_session
            state.last_cycle_at = now
            state.mode = self.settings.mode.value

            open_positions = session.scalar(
                select(func.count(TradeRecord.id)).where(TradeRecord.status.in_(["open", "partially_closed"]))
            )
            state.open_positions = int(open_positions or 0)
            state.daily_drawdown = self.risk_manager.daily_drawdown(self._todays_realized_pnls(session, now))

            if not active_session:
                return {
                    "evaluated_symbols": 0,
                    "opened_trades": 0,
                    "blocked_by_filters": 0,
                }

            events = self.news_provider.upcoming_events(session, now)
            realized_pnls = self._todays_realized_pnls(session, now)
            session_trade_count = self._session_trade_count(session, active_session, now)

            for market, symbols in (
                (MarketType.FOREX, self.settings.forex_symbols),
                (MarketType.CRYPTO, self.settings.crypto_symbols),
            ):
                feed = self.data_feeds.get(market)
                executor = self.execution_adapters.get(market)
                if not feed or not executor:
                    continue

                for symbol in symbols:
                    evaluated_symbols += 1
                    try:
                        h1 = feed.get_ohlcv(symbol, "1h", 300)
                        m15 = feed.get_ohlcv(symbol, "15m", 300)
                        m5 = feed.get_ohlcv(symbol, "5m", 300)
                    except Exception as exc:
                        logger.warning("Data fetch failed for %s: %s", symbol, exc)
                        continue

                    _, signal = detect_execution_setup(
                        symbol=symbol,
                        market=market,
                        h1_frame=h1,
                        m15_frame=m15,
                        m5_frame=m5,
                        session=active_session,
                    )
                    if signal is None:
                        continue

                    signal.confidence = self.ai_model.score(signal)
                    session.add(
                        SignalRecord(
                            symbol=signal.symbol,
                            market=signal.market.value,
                            direction=signal.direction.value,
                            reason=signal.reason,
                            h1_bias=signal.h1_bias,
                            m15_trend=signal.m15_trend,
                            session=signal.session,
                            entry_price=signal.entry_price,
                            stop_loss=signal.stop_loss,
                            take_profit_levels=signal.take_profit_levels,
                            atr=signal.atr,
                            confidence=signal.confidence,
                            features=signal.features,
                        )
                    )

                    if signal.confidence < self.settings.confidence_threshold:
                        blocked_by_filters += 1
                        continue
                    if self.news_filter.is_blocked(
                        market=market,
                        symbol=symbol,
                        now=now,
                        events=events,
                    ):
                        blocked_by_filters += 1
                        continue

                    risk_check = self.risk_manager.can_open_trade(
                        session_trade_count=session_trade_count,
                        open_positions=int(open_positions or 0),
                        realized_pnls=realized_pnls,
                    )
                    if not risk_check.allowed:
                        blocked_by_filters += 1
                        continue

                    try:
                        spec = feed.instrument_spec(symbol)
                        plan = self.risk_manager.build_position_plan(signal, spec)
                        plan.metadata["point_value"] = spec.point_value
                    except Exception as exc:
                        logger.warning("Plan build failed for %s: %s", symbol, exc)
                        blocked_by_filters += 1
                        continue

                    try:
                        result = executor.place_trade(plan)
                    except Exception as exc:
                        logger.warning("Execution failed for %s: %s", symbol, exc)
                        blocked_by_filters += 1
                        continue

                    session.add(
                        TradeRecord(
                            broker_trade_id=result.broker_trade_id,
                            symbol=plan.symbol,
                            market=plan.market.value,
                            direction=plan.direction.value,
                            session=plan.session,
                            status=result.status,
                            mode=self.settings.mode.value,
                            entry_price=plan.entry_price,
                            stop_loss=plan.stop_loss,
                            take_profit_levels=plan.take_profit_levels,
                            quantity=plan.quantity,
                            remaining_quantity=plan.quantity,
                            risk_amount=plan.risk_amount,
                            confidence=plan.confidence,
                            realized_pnl=0.0,
                            metadata_json=plan.metadata,
                        )
                    )
                    session_trade_count += 1
                    open_positions = int(open_positions or 0) + 1
                    opened_trades += 1

            state.open_positions = int(open_positions or 0)
            state.daily_drawdown = self.risk_manager.daily_drawdown(self._todays_realized_pnls(session, now))

        return {
            "evaluated_symbols": evaluated_symbols,
            "opened_trades": opened_trades,
            "blocked_by_filters": blocked_by_filters,
        }

    def _manage_open_positions(self, session) -> None:
        trades = session.scalars(
            select(TradeRecord).where(TradeRecord.status.in_(["open", "partially_closed"]))
        ).all()
        for trade in trades:
            market = MarketType(trade.market)
            feed = self.data_feeds.get(market)
            executor = self.execution_adapters.get(market)
            if not feed or not executor:
                continue

            try:
                price = feed.current_price(trade.symbol)
            except Exception as exc:
                logger.warning("Price fetch failed for %s: %s", trade.symbol, exc)
                continue

            point_value = float(trade.metadata_json.get("point_value", 1.0))
            direction_sign = 1 if trade.direction == "long" else -1

            def pnl(exit_price: float, qty: float) -> float:
                return (exit_price - trade.entry_price) * qty * point_value * direction_sign

            stop_hit = price <= trade.stop_loss if direction_sign == 1 else price >= trade.stop_loss
            tp1, tp2, tp3 = [float(level) for level in trade.take_profit_levels]
            tp1_hit = price >= tp1 if direction_sign == 1 else price <= tp1
            tp2_hit = price >= tp2 if direction_sign == 1 else price <= tp2
            tp3_hit = price >= tp3 if direction_sign == 1 else price <= tp3

            tranche = round(trade.quantity / 3.0, 8)

            if stop_hit:
                remaining = trade.remaining_quantity
                if remaining > 0:
                    executor.close_partial(trade, remaining)
                    trade.realized_pnl += pnl(trade.stop_loss, remaining)
                trade.remaining_quantity = 0.0
                trade.status = "closed"
                trade.closed_at = datetime.now(timezone.utc)
                continue

            if tp1_hit and not trade.tp1_hit:
                close_qty = min(tranche, trade.remaining_quantity)
                if close_qty > 0:
                    executor.close_partial(trade, close_qty)
                    trade.remaining_quantity -= close_qty
                    trade.realized_pnl += pnl(tp1, close_qty)
                trade.tp1_hit = True
                trade.moved_to_break_even = True
                trade.stop_loss = trade.entry_price
                executor.modify_stop(trade, trade.entry_price)
                trade.status = "partially_closed"

            if tp2_hit and trade.tp1_hit and not trade.tp2_hit:
                close_qty = min(tranche, trade.remaining_quantity)
                if close_qty > 0:
                    executor.close_partial(trade, close_qty)
                    trade.remaining_quantity -= close_qty
                    trade.realized_pnl += pnl(tp2, close_qty)
                trade.tp2_hit = True
                trade.status = "partially_closed"

            if tp3_hit and not trade.tp3_hit:
                close_qty = trade.remaining_quantity
                if close_qty > 0:
                    executor.close_partial(trade, close_qty)
                    trade.remaining_quantity = 0.0
                    trade.realized_pnl += pnl(tp3, close_qty)
                trade.tp3_hit = True
                trade.status = "closed"
                trade.closed_at = datetime.now(timezone.utc)

    def get_status(self) -> BotStateRecord:
        with self.database.session() as session:
            return self._ensure_state(session)

    def list_trades(self, limit: int = 20) -> list[TradeRecord]:
        with self.database.session() as session:
            return list(
                session.scalars(
                    select(TradeRecord).order_by(TradeRecord.opened_at.desc()).limit(limit)
                ).all()
            )

    def list_signals(self, limit: int = 20) -> list[SignalRecord]:
        with self.database.session() as session:
            return list(
                session.scalars(
                    select(SignalRecord).order_by(SignalRecord.created_at.desc()).limit(limit)
                ).all()
            )
