import asyncio
import logging
from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.model import TradeConfidenceModel
from app.config import Settings
from app.data.market_data import MarketDataGateway
from app.execution.base import BrokerExecutor, OrderRequest
from app.execution.binance_executor import BinanceExecutor
from app.execution.mt5_executor import MT5Executor
from app.execution.paper_executor import PaperExecutor
from app.filters.news import HighImpactNewsFilter
from app.filters.session import SessionFilter
from app.models.entities import Trade, TradeSignal
from app.risk.manager import RiskManager, RiskProfile
from app.strategy.multi_timeframe import TimeframeContext, analyze_signal
from app.trading.position_manager import ManagedPosition, PositionManager

logger = logging.getLogger(__name__)


class TradingEngine:
    def __init__(self, settings: Settings, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.mode = settings.mode
        self._running = False
        self._task: asyncio.Task | None = None
        self.last_cycle_at: datetime | None = None

        self.session_filter = SessionFilter()
        self.news_filter = HighImpactNewsFilter(settings.news_block_window_minutes)
        self.risk_manager = RiskManager(
            RiskProfile(
                account_balance=settings.account_balance,
                risk_per_trade_pct=settings.risk_per_trade_pct,
                max_drawdown_pct=settings.max_drawdown_pct,
                max_trades_per_session=settings.max_trades_per_session,
            )
        )
        self.model = TradeConfidenceModel(settings.model_path, settings.min_confidence_to_trade)
        self.market_data = MarketDataGateway(
            settings.binance_api_key,
            settings.binance_api_secret,
            settings.binance_testnet,
        )
        self.position_manager = PositionManager()

        self.paper_executor = PaperExecutor()
        self.crypto_live_executor: BrokerExecutor = (
            BinanceExecutor(settings.binance_api_key, settings.binance_api_secret, settings.binance_testnet)
            if settings.binance_api_key and settings.binance_api_secret
            else self.paper_executor
        )
        self.forex_live_executor: BrokerExecutor = (
            MT5Executor(
                login=settings.mt5_login,
                password=settings.mt5_password,
                server=settings.mt5_server,
                path=settings.mt5_path,
            )
            if settings.mt5_login and settings.mt5_password and settings.mt5_server
            else self.paper_executor
        )

    @property
    def running(self) -> bool:
        return self._running

    async def start(self, mode: str | None = None) -> None:
        if self._running:
            return
        if mode:
            self.mode = mode
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Trading engine started in %s mode", self.mode)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            await self._task
            self._task = None
        logger.info("Trading engine stopped")

    async def trades_today(self) -> int:
        today = datetime.now(tz=timezone.utc).date()
        async with self.session_factory() as session:
            stmt = select(func.count(Trade.id)).where(func.date(Trade.opened_at) == today)
            count = await session.scalar(stmt)
            return int(count or 0)

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await self._cycle()
            except Exception as exc:  # pragma: no cover
                logger.exception("Engine cycle error: %s", exc)
            await asyncio.sleep(self.settings.polling_interval_seconds)

    async def _cycle(self) -> None:
        now_utc = datetime.now(tz=timezone.utc)
        self.last_cycle_at = now_utc
        if not self.session_filter.is_allowed(now_utc):
            logger.info("Outside London/New York sessions, cycle skipped.")
            return

        for symbol in self.settings.symbols_forex:
            await self._process_symbol(symbol=symbol, market="forex", now_utc=now_utc)
        for symbol in self.settings.symbols_crypto:
            await self._process_symbol(symbol=symbol, market="crypto", now_utc=now_utc)

    async def _process_symbol(self, symbol: str, market: str, now_utc: datetime) -> None:
        async with self.session_factory() as db:
            if not self.risk_manager.can_open_trade(now_utc):
                logger.warning("Risk guard blocked new trade for %s", symbol)
                return
            if not await self.news_filter.is_allowed(db, symbol, now_utc):
                logger.info("News guard blocked trade for %s", symbol)
                return

            df_h1 = await self.market_data.get_ohlcv(symbol, market, "H1", bars=300)
            df_m15 = await self.market_data.get_ohlcv(symbol, market, "M15", bars=300)
            df_m5 = await self.market_data.get_ohlcv(symbol, market, "M5", bars=300)
            context, signal = analyze_signal(
                df_h1=df_h1,
                df_m15=df_m15,
                df_m5=df_m5,
                atr_period=self.settings.atr_period,
                atr_multiplier=self.settings.atr_multiplier,
                stop_type=self.settings.stop_type,
            )
            self._manage_open_position(symbol, market, float(df_m5.iloc[-1]["close"]))
            if signal is None:
                return

            features = self._build_features(context, df_h1, df_m15, df_m5)
            confidence = self.model.score(features)
            signal_id = await self._store_signal(
                db,
                symbol=symbol,
                market=market,
                side=signal.side,
                confidence=confidence.confidence,
                context=context,
                payload={
                    "entry": signal.entry,
                    "stop_loss": signal.stop_loss,
                    "reasons": signal.reasons,
                    "features": features,
                },
            )
            if not confidence.accepted:
                return
            await self._open_trade(db, signal_id, symbol, market, signal, confidence.confidence)

    def _manage_open_position(self, symbol: str, market: str, current_price: float) -> None:
        self.position_manager.on_price(symbol, market, current_price)

    def _build_features(self, context: TimeframeContext, df_h1, df_m15, df_m5) -> dict[str, float]:
        h1_returns = df_h1["close"].pct_change().tail(20).dropna()
        m15_returns = df_m15["close"].pct_change().tail(20).dropna()
        m5_range = (df_m5["high"] - df_m5["low"]).tail(20)
        return {
            "h1_bias_bullish": 1.0 if context.h1_bias == "bullish" else 0.0,
            "m15_aligned": 1.0 if context.m15_structure == "aligned" else 0.0,
            "m5_triggered": 1.0 if context.m5_triggered else 0.0,
            "h1_volatility": float(h1_returns.std() if len(h1_returns) else 0.0),
            "m15_volatility": float(m15_returns.std() if len(m15_returns) else 0.0),
            "m5_avg_range": float(m5_range.mean()),
            "structure_alignment": 1.0 if context.h1_bias in {"bullish", "bearish"} and context.m15_structure == "aligned" else 0.0,
            "session_score": 1.0,
        }

    async def _open_trade(
        self,
        db: AsyncSession,
        signal_id: int,
        symbol: str,
        market: str,
        signal,
        confidence: float,
    ) -> None:
        qty = self.risk_manager.position_size(signal.entry, signal.stop_loss)
        if qty <= 0:
            return
        take_profits = PositionManager.build_take_profits(signal.entry, signal.stop_loss, signal.side)
        order = OrderRequest(
            symbol=symbol,
            market=market,  # type: ignore[arg-type]
            side=signal.side,
            quantity=round(qty, 4),
            entry_price=signal.entry,
            stop_loss=signal.stop_loss,
            take_profits=take_profits,
            meta={"confidence": confidence},
        )
        executor = self._select_executor(market)
        result = await executor.submit_order(order)
        trade = Trade(
            signal_id=signal_id,
            symbol=symbol,
            market=market,
            side=signal.side,
            mode=self.mode,
            entry_price=signal.entry,
            stop_loss=signal.stop_loss,
            take_profit_1=take_profits[0],
            take_profit_2=take_profits[1],
            take_profit_3=take_profits[2],
            position_size=order.quantity,
            status="open",
            meta={"execution": result.raw, "confidence": confidence},
        )
        db.add(trade)
        await db.commit()
        self.risk_manager.mark_trade_opened(datetime.now(tz=timezone.utc))
        self.position_manager.add(
            ManagedPosition(
                symbol=symbol,
                market=market,
                side=signal.side,
                entry=signal.entry,
                stop_loss=signal.stop_loss,
                take_profits=take_profits,
                quantity=order.quantity,
                opened_at=datetime.now(tz=timezone.utc),
            )
        )

    def _select_executor(self, market: str) -> BrokerExecutor:
        if self.mode == "paper":
            return self.paper_executor
        if market == "crypto":
            return self.crypto_live_executor
        return self.forex_live_executor

    async def _store_signal(
        self,
        db: AsyncSession,
        symbol: str,
        market: str,
        side: str,
        confidence: float,
        context: TimeframeContext,
        payload: dict,
    ) -> int:
        signal = TradeSignal(
            symbol=symbol,
            market=market,
            side=side,
            confidence=confidence,
            timeframe_context=asdict(context),
            signal_payload=payload,
        )
        db.add(signal)
        await db.flush()
        await db.commit()
        return signal.id
