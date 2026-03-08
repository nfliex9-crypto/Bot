from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Dict, Iterable, List

from sqlalchemy import func, select

from app.ai.service import AIService
from app.config import Settings
from app.db import get_db_session
from app.filters.news import NewsFilter
from app.filters.session import SessionFilter
from app.market_data import MultiMarketDataService
from app.models import AccountSnapshot, Trade, TradeFeature
from app.risk.manager import RiskManager
from app.schemas import Signal
from app.services.trade_service import MarketTick, TradeService
from app.strategy.liquidity_bos_pullback import LiquiditySweepBOSPullbackStrategy, StrategyContext

logger = logging.getLogger(__name__)


class TradingEngine:
    def __init__(self, settings: Settings, trade_service: TradeService):
        self.settings = settings
        self.trade_service = trade_service
        self.strategy = LiquiditySweepBOSPullbackStrategy(settings)
        self.ai_service = AIService(settings)
        self.risk = RiskManager(settings)
        self.market_data = MultiMarketDataService(settings)
        self.news_filter = NewsFilter(settings)
        self.session_filter = SessionFilter(settings)

        self._running = False
        self._task: asyncio.Task | None = None

    @property
    def running(self) -> bool:
        return self._running

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._runner(), name="trading-engine")
        logger.info("Trading engine started.")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Trading engine stopped.")

    async def _runner(self) -> None:
        while self._running:
            try:
                await self.run_once()
            except Exception as exc:
                logger.exception("Engine cycle failed: %s", exc)
            await asyncio.sleep(self.settings.polling_seconds)

    def _symbol_currencies(self, market: str, symbol: str) -> List[str]:
        if market == "forex" and len(symbol) >= 6:
            return [symbol[:3], symbol[3:6]]
        if market == "crypto":
            return ["USD"]
        return []

    def _all_symbols(self) -> Iterable[tuple[str, str]]:
        for sym in self.settings.forex_symbols:
            yield "forex", sym
        for sym in self.settings.crypto_symbols:
            yield "crypto", sym

    def _snapshot(self, now: datetime) -> None:
        with get_db_session() as session:
            realized = session.scalar(select(func.coalesce(func.sum(Trade.realized_pnl), 0.0))) or 0.0
            equity = self.settings.account_balance + float(realized)
            drawdown = max(0.0, (self.settings.account_balance - equity) / self.settings.account_balance)
            snap = AccountSnapshot(
                balance=self.settings.account_balance,
                equity=equity,
                drawdown=drawdown,
                metadata_json={"time": now.isoformat()},
            )
            session.add(snap)

    def _sync_training_labels(self) -> None:
        with get_db_session() as session:
            rows = session.execute(
                select(TradeFeature, Trade).join(Trade, TradeFeature.trade_id == Trade.id).where(Trade.status != "open")
            ).all()
            for feature_row, trade in rows:
                feature_row.label = 1 if trade.realized_pnl > 0 else 0
                session.add(feature_row)

    async def run_once(self) -> None:
        now = datetime.now(UTC)
        if not self.session_filter.allow(now):
            logger.info("Outside London/New York sessions; skipping cycle.")
            return

        with get_db_session() as session:
            for market, symbol in self._all_symbols():
                mtf = self.market_data.fetch_mtf(market, symbol)
                last_price = float(mtf["M5"]["close"].iloc[-1])
                self.trade_service.update_open_trades(session, MarketTick(symbol=symbol, price=last_price))

                allowed, reason = self.risk.can_trade(session)
                if not allowed:
                    logger.warning("Risk blocked trade for %s: %s", symbol, reason)
                    continue

                currencies = self._symbol_currencies(market, symbol)
                if self.news_filter.should_block(currencies, now):
                    logger.info("News filter blocked %s", symbol)
                    continue

                signal = self.strategy.generate_signal(
                    StrategyContext(
                        market=market,
                        symbol=symbol,
                        df_h1=mtf["H1"],
                        df_m15=mtf["M15"],
                        df_m5=mtf["M5"],
                    )
                )
                if signal is None:
                    continue
                self._try_open_trade(session, signal)

        self._sync_training_labels()
        self._snapshot(now)

    def _try_open_trade(self, session, signal: Signal) -> None:
        confidence = self.ai_service.score(signal.feature_payload, signal.rule_score)
        if confidence < self.settings.min_confidence_to_trade:
            logger.info("Confidence %.2f below threshold for %s", confidence, signal.symbol)
            return
        qty = self.risk.compute_position_size(signal.entry_price, signal.stop_loss)
        if qty <= 0:
            logger.info("Position size is zero for %s", signal.symbol)
            return

        trade = self.trade_service.open_trade(session, signal=signal, quantity=qty, confidence=confidence)
        if trade is None:
            logger.warning("Order failed for %s", signal.symbol)
            return
        session.add(
            TradeFeature(
                trade_id=trade.id,
                features=signal.feature_payload,
                label=0,
            )
        )
        logger.info("Opened %s %s trade id=%s confidence=%.2f", signal.side, signal.symbol, trade.id, confidence)

