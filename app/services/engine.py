from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.init_db import ensure_bot_state
from app.db.models import BotState, SignalRecord, TradeRecord
from app.db.session import db_session
from app.domain.models import Market, TradeDirection, TradeSetup, TradeStatus
from app.services.ai import RandomForestConfidenceModel, TradeFeatureEngineer
from app.services.execution import ExecutionRouter
from app.services.filters import TradingFilters
from app.services.market_data import BinanceMarketDataProvider, MT5MarketDataProvider
from app.services.risk import RiskManager
from app.services.strategy import LiquiditySweepBosPullbackStrategy


logger = logging.getLogger(__name__)


class TradingEngine:
    def __init__(
        self,
        settings: Settings,
        strategy: LiquiditySweepBosPullbackStrategy,
        ai_model: RandomForestConfidenceModel,
        filters: TradingFilters,
        risk_manager: RiskManager,
        execution_router: ExecutionRouter,
    ) -> None:
        self.settings = settings
        self.strategy = strategy
        self.ai_model = ai_model
        self.filters = filters
        self.risk_manager = risk_manager
        self.execution_router = execution_router
        self.forex_provider = MT5MarketDataProvider(settings)
        self.crypto_provider = BinanceMarketDataProvider(settings)

    def run_forever(self) -> None:
        while True:
            try:
                self.run_cycle()
            except Exception:
                logger.exception("Worker cycle failed")
            time.sleep(self.settings.worker_poll_seconds)

    def run_cycle(self) -> None:
        now = datetime.now(timezone.utc)
        with db_session() as session:
            state = ensure_bot_state(session)
            self._manage_open_trades(session)
            self._refresh_state(session, state, now)

            drawdown_check = self.risk_manager.validate_drawdown(state.current_equity, state.peak_equity)
            if not drawdown_check.allowed:
                state.trading_enabled = False
                state.notes = drawdown_check.reason
                logger.warning("Trading disabled: %s", drawdown_check.reason)
                return

            if not state.trading_enabled:
                logger.info("Trading is disabled; skipping entries")
                return

            self._scan_market(session, state, Market.FOREX, self.settings.forex_symbols)
            self._scan_market(session, state, Market.CRYPTO, self.settings.crypto_symbols)
            self._refresh_state(session, state, now)

    def _scan_market(self, session: Session, state: BotState, market: Market, symbols: list[str]) -> None:
        provider = self.forex_provider if market == Market.FOREX else self.crypto_provider

        for symbol in symbols:
            try:
                snapshot = provider.fetch_snapshot(symbol)
                setup = self.strategy.generate_setup(snapshot)
                if setup is None:
                    continue

                filter_result = self.filters.evaluate(market=market, symbol=symbol, now=snapshot.timestamp)
                setup.session_label = filter_result.session_label
                features = TradeFeatureEngineer.build(setup, snapshot, filter_result)
                ai_confidence = self.ai_model.score(features, setup.strategy_score)
                confidence = round((setup.strategy_score * 0.4) + (ai_confidence * 0.6), 4)
                setup.ai_confidence = ai_confidence
                setup.confidence = confidence

                self._store_signal(
                    session=session,
                    setup=setup,
                    features=features,
                    passed_filters=filter_result.passed,
                    blocked_reason=filter_result.blocked_reason,
                )

                if not filter_result.passed:
                    continue
                if confidence < self.settings.confidence_threshold:
                    continue
                if self._has_open_trade(session, symbol):
                    continue

                trades_this_session = self._count_session_trades(session, setup.session_label)
                trade_limit = self.risk_manager.validate_trade_limit(trades_this_session)
                if not trade_limit.allowed:
                    logger.info("Trade blocked for %s: %s", symbol, trade_limit.reason)
                    continue

                quantity = self.risk_manager.position_size(
                    equity=state.current_equity,
                    entry_price=setup.entry_price,
                    stop_loss=setup.stop_loss,
                )
                if quantity <= 0:
                    continue

                execution = self.execution_router.place_trade(setup, quantity)
                if not execution.accepted:
                    continue

                risk_amount = self.risk_manager.risk_amount(state.current_equity)
                trade = TradeRecord(
                    market=market.value,
                    symbol=symbol,
                    mode=execution.mode.value,
                    direction=setup.direction.value,
                    status=TradeStatus.OPEN.value,
                    session_label=setup.session_label,
                    venue=execution.venue,
                    provider_order_id=execution.provider_order_id,
                    entry_price=setup.entry_price,
                    executed_price=execution.executed_price,
                    initial_stop_loss=setup.stop_loss,
                    current_stop_loss=setup.stop_loss,
                    tp1=setup.take_profit_1,
                    tp2=setup.take_profit_2,
                    tp3=setup.take_profit_3,
                    requested_quantity=quantity,
                    executed_quantity=execution.executed_quantity,
                    remaining_quantity=execution.executed_quantity,
                    risk_amount=risk_amount,
                    strategy_score=setup.strategy_score,
                    ai_confidence=setup.ai_confidence,
                    confidence=setup.confidence,
                    structure_level=setup.structure_level,
                    atr_value=setup.atr_value,
                    rationale=setup.rationale,
                    feature_vector=features,
                    details={**setup.metadata, **execution.details},
                )
                session.add(trade)
                session.flush()
                logger.info("Opened %s %s %s", market.value, symbol, setup.direction.value)
            except Exception:
                logger.exception("Failed processing %s %s", market.value, symbol)

    def _manage_open_trades(self, session: Session) -> None:
        open_statuses = [TradeStatus.OPEN.value, TradeStatus.PARTIAL.value]
        trades = session.scalars(select(TradeRecord).where(TradeRecord.status.in_(open_statuses))).all()

        for trade in trades:
            market = Market(trade.market)
            provider = self.forex_provider if market == Market.FOREX else self.crypto_provider
            direction = TradeDirection(trade.direction)
            price = provider.current_price(trade.symbol)
            trade.unrealized_pnl = round(self._directional_pnl(direction, trade.executed_price, price, trade.remaining_quantity), 4)

            if direction == TradeDirection.LONG:
                self._process_long_trade(session, trade, price)
            else:
                self._process_short_trade(session, trade, price)

    def _process_long_trade(self, session: Session, trade: TradeRecord, price: float) -> None:
        if price <= trade.current_stop_loss and trade.remaining_quantity > 0:
            self._close_remaining(session, trade, price, reason="stop_loss")
            return
        if not trade.tp1_hit and price >= trade.tp1:
            self._take_partial(trade, trade.tp1, 0.4, "tp1")
        if not trade.tp2_hit and price >= trade.tp2 and trade.remaining_quantity > 0:
            self._take_partial(trade, trade.tp2, 0.3, "tp2")
        if not trade.tp3_hit and price >= trade.tp3 and trade.remaining_quantity > 0:
            self._close_remaining(session, trade, trade.tp3, reason="tp3")

    def _process_short_trade(self, session: Session, trade: TradeRecord, price: float) -> None:
        if price >= trade.current_stop_loss and trade.remaining_quantity > 0:
            self._close_remaining(session, trade, price, reason="stop_loss")
            return
        if not trade.tp1_hit and price <= trade.tp1:
            self._take_partial(trade, trade.tp1, 0.4, "tp1")
        if not trade.tp2_hit and price <= trade.tp2 and trade.remaining_quantity > 0:
            self._take_partial(trade, trade.tp2, 0.3, "tp2")
        if not trade.tp3_hit and price <= trade.tp3 and trade.remaining_quantity > 0:
            self._close_remaining(session, trade, trade.tp3, reason="tp3")

    def _take_partial(self, trade: TradeRecord, exit_price: float, fraction: float, label: str) -> None:
        quantity = round(trade.executed_quantity * fraction, 6)
        quantity = min(quantity, trade.remaining_quantity)
        if quantity <= 0:
            return

        market = Market(trade.market)
        direction = TradeDirection(trade.direction)
        self.execution_router.close_quantity(market, trade.symbol, direction, quantity)
        trade.realized_pnl = round(
            trade.realized_pnl + self._directional_pnl(direction, trade.executed_price, exit_price, quantity),
            4,
        )
        trade.remaining_quantity = round(trade.remaining_quantity - quantity, 6)
        trade.status = TradeStatus.PARTIAL.value if trade.remaining_quantity > 0 else TradeStatus.CLOSED.value

        if label == "tp1":
            trade.tp1_hit = True
            trade.break_even_applied = True
            trade.current_stop_loss = trade.executed_price
        elif label == "tp2":
            trade.tp2_hit = True
        trade.details[f"{label}_price"] = exit_price

    def _close_remaining(self, session: Session, trade: TradeRecord, exit_price: float, reason: str) -> None:
        if trade.remaining_quantity <= 0:
            trade.status = TradeStatus.CLOSED.value
            trade.closed_at = datetime.now(timezone.utc)
            return

        market = Market(trade.market)
        direction = TradeDirection(trade.direction)
        quantity = trade.remaining_quantity
        self.execution_router.close_quantity(market, trade.symbol, direction, quantity)
        trade.realized_pnl = round(
            trade.realized_pnl + self._directional_pnl(direction, trade.executed_price, exit_price, quantity),
            4,
        )
        trade.remaining_quantity = 0.0
        trade.unrealized_pnl = 0.0
        trade.status = TradeStatus.CLOSED.value
        trade.closed_at = datetime.now(timezone.utc)
        if reason == "tp3":
            trade.tp3_hit = True
        trade.details["closed_reason"] = reason
        session.add(trade)

    def _store_signal(
        self,
        session: Session,
        setup: TradeSetup,
        features: dict[str, float],
        passed_filters: bool,
        blocked_reason: str | None,
    ) -> None:
        signal = SignalRecord(
            market=setup.market.value,
            symbol=setup.symbol,
            direction=setup.direction.value,
            status="candidate" if passed_filters else "blocked",
            confidence=setup.confidence,
            ai_confidence=setup.ai_confidence,
            strategy_score=setup.strategy_score,
            passed_filters=passed_filters,
            blocked_reason=blocked_reason,
            rationale=setup.rationale,
            payload={
                "entry_price": setup.entry_price,
                "stop_loss": setup.stop_loss,
                "tp1": setup.take_profit_1,
                "tp2": setup.take_profit_2,
                "tp3": setup.take_profit_3,
                "session_label": setup.session_label,
                "features": features,
                **setup.metadata,
            },
        )
        session.add(signal)

    def _refresh_state(self, session: Session, state: BotState, now: datetime) -> None:
        open_statuses = [TradeStatus.OPEN.value, TradeStatus.PARTIAL.value]
        realized = session.scalar(select(func.coalesce(func.sum(TradeRecord.realized_pnl), 0.0))) or 0.0
        unrealized = session.scalar(
            select(func.coalesce(func.sum(TradeRecord.unrealized_pnl), 0.0)).where(TradeRecord.status.in_(open_statuses))
        ) or 0.0
        open_positions = session.scalar(
            select(func.count()).select_from(TradeRecord).where(TradeRecord.status.in_(open_statuses))
        ) or 0

        state.current_equity = round(self.settings.account_balance + float(realized) + float(unrealized), 4)
        state.peak_equity = max(state.peak_equity, state.current_equity)
        if state.peak_equity > 0:
            state.current_drawdown = round(
                max((state.peak_equity - state.current_equity) / state.peak_equity, 0.0),
                6,
            )
        state.open_positions = int(open_positions)
        state.last_cycle_at = now

    def _count_session_trades(self, session: Session, session_label: str) -> int:
        day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        count = session.scalar(
            select(func.count())
            .select_from(TradeRecord)
            .where(TradeRecord.session_label == session_label)
            .where(TradeRecord.opened_at >= day_start)
        )
        return int(count or 0)

    @staticmethod
    def _has_open_trade(session: Session, symbol: str) -> bool:
        open_statuses = [TradeStatus.OPEN.value, TradeStatus.PARTIAL.value]
        trade = session.scalar(
            select(TradeRecord).where(TradeRecord.symbol == symbol).where(TradeRecord.status.in_(open_statuses))
        )
        return trade is not None

    @staticmethod
    def _directional_pnl(direction: TradeDirection, entry: float, exit_price: float, quantity: float) -> float:
        if direction == TradeDirection.LONG:
            return (exit_price - entry) * quantity
        return (entry - exit_price) * quantity
