from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.ai.model import TradeConfidenceModel
from app.config import Settings
from app.db.models import BotState, Trade
from app.db.session import SessionLocal
from app.execution.base import OrderRequest
from app.execution.router import ExecutionRouter
from app.market.data_provider import MarketDataProvider
from app.risk.manager import RiskManager
from app.services.news_filter import NewsFilter
from app.services.session_filter import SessionFilter
from app.services.trade_manager import TradeManager
from app.strategy.liquidity_bos_pullback import LiquidityBosPullbackStrategy

logger = logging.getLogger(__name__)


class BotService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.market = MarketDataProvider(settings)
        self.strategy = LiquidityBosPullbackStrategy(settings)
        self.risk = RiskManager(settings)
        self.ai = TradeConfidenceModel(settings)
        self.execution = ExecutionRouter(settings)
        self.news_filter = NewsFilter(settings)
        self.session_filter = SessionFilter(settings)
        self.trade_manager = TradeManager(self.risk)

        self.running = True
        self.last_cycle_timestamp: datetime | None = None
        self.last_cycle_notes: list[str] = []
        self.confidence_threshold = 0.60

    def set_running(self, running: bool) -> None:
        self.running = running

    def status(self) -> dict:
        db = SessionLocal()
        try:
            open_trades = db.query(Trade).filter(Trade.status == "open").count()
            state = db.query(BotState).first()
            equity = state.current_equity if state else self.risk.current_equity
            dd = state.drawdown_pct if state else self.risk.drawdown_pct
            return {
                "running": self.running,
                "mode": self.settings.trading_mode,
                "equity": equity,
                "drawdown_pct": dd,
                "open_trades": open_trades,
                "last_cycle_timestamp": self.last_cycle_timestamp,
                "last_cycle_notes": self.last_cycle_notes[-15:],
            }
        finally:
            db.close()

    def _sync_state(self, db: Session) -> None:
        state = db.query(BotState).first()
        if not state:
            state = BotState(
                running=self.running,
                current_equity=self.risk.current_equity,
                drawdown_pct=self.risk.drawdown_pct,
            )
        else:
            state.running = self.running
            state.current_equity = self.risk.current_equity
            state.drawdown_pct = self.risk.drawdown_pct
        db.add(state)
        db.commit()

    def _latest_price_snapshot(self, symbols: list[tuple[str, str]]) -> dict[str, float]:
        prices: dict[str, float] = {}
        for symbol, market_type in symbols:
            df = self.market.get_timeframe_data(symbol, market_type, self.settings.timeframe_execution, bars=10)
            if df.empty:
                continue
            prices[symbol] = float(df["close"].iloc[-1])
        return prices

    def run_cycle(self) -> list[str]:
        notes: list[str] = []
        now = datetime.now(timezone.utc)
        db = SessionLocal()
        try:
            targets = [(s, "forex") for s in self.settings.forex_symbols] + [(s, "crypto") for s in self.settings.crypto_symbols]

            # Manage open trades first (TP/SL/BE progression).
            price_snapshot = self._latest_price_snapshot(targets)
            notes.extend(self.trade_manager.manage_open_trades(db, price_snapshot))

            if not self.running:
                notes.append("Bot is paused")
                self.last_cycle_notes = notes
                self.last_cycle_timestamp = now
                self._sync_state(db)
                return notes

            if not self.session_filter.is_active(now):
                notes.append("Outside London/New York sessions")
                self.last_cycle_notes = notes
                self.last_cycle_timestamp = now
                self._sync_state(db)
                return notes

            blocked, reason = self.news_filter.has_blocking_news()
            notes.append(reason)
            if blocked:
                self.last_cycle_notes = notes
                self.last_cycle_timestamp = now
                self._sync_state(db)
                return notes

            for symbol, market_type in targets:
                if db.query(Trade).filter(Trade.symbol == symbol, Trade.status == "open").count() > 0:
                    notes.append(f"{symbol}: skipped (open trade exists)")
                    continue

                risk_decision = self.risk.can_open_trade(now)
                if not risk_decision.allowed:
                    notes.append(f"{symbol}: blocked by risk manager ({risk_decision.reason})")
                    break

                df_h1 = self.market.get_timeframe_data(symbol, market_type, self.settings.timeframe_bias)
                df_m15 = self.market.get_timeframe_data(symbol, market_type, self.settings.timeframe_structure)
                df_m5 = self.market.get_timeframe_data(symbol, market_type, self.settings.timeframe_execution)

                if df_h1.empty or df_m15.empty or df_m5.empty:
                    notes.append(f"{symbol}: missing market data")
                    continue

                setup = self.strategy.analyze(df_h1, df_m15, df_m5)
                if not setup.should_trade:
                    notes.append(f"{symbol}: no setup ({'; '.join(setup.notes or [])})")
                    continue

                confidence = self.ai.score(setup.confidence_features or {})
                if confidence < self.confidence_threshold:
                    notes.append(f"{symbol}: confidence {confidence:.2f} below threshold")
                    continue

                quantity = self.risk.compute_position_size(setup.entry, setup.stop_loss, market_type=market_type)
                if quantity <= 0:
                    notes.append(f"{symbol}: invalid position size")
                    continue

                order_req = OrderRequest(
                    symbol=symbol,
                    market_type=market_type,
                    side=setup.side,
                    quantity=quantity,
                    entry_price=setup.entry,
                    stop_loss=setup.stop_loss,
                    tp1=setup.tp1,
                    tp2=setup.tp2,
                    tp3=setup.tp3,
                    confidence=confidence,
                    metadata={"notes": setup.notes or [], "features": setup.confidence_features or {}},
                )
                result = self.execution.execute(order_req)
                if not result.accepted:
                    notes.append(f"{symbol}: order rejected ({result.message})")
                    continue

                trade = Trade(
                    symbol=symbol,
                    market_type=market_type,
                    side=setup.side,
                    mode=self.settings.trading_mode,
                    status="open",
                    confidence=confidence,
                    entry_price=setup.entry,
                    stop_loss=setup.stop_loss,
                    tp1=setup.tp1,
                    tp2=setup.tp2,
                    tp3=setup.tp3,
                    position_size=quantity,
                    risk_amount=self.risk.risk_amount,
                    execution_payload=result.raw,
                    metadata_json={
                        "execution_id": result.order_id,
                        "setup_notes": setup.notes or [],
                        "features": setup.confidence_features or {},
                    },
                )
                db.add(trade)
                db.commit()
                self.risk.register_open_trade(now)
                notes.append(f"{symbol}: trade opened ({setup.side}) confidence={confidence:.2f}")

            self.last_cycle_notes = notes
            self.last_cycle_timestamp = now
            self._sync_state(db)
            return notes
        except Exception as exc:
            logger.exception("Bot cycle failed: %s", exc)
            notes.append(f"Cycle error: {exc}")
            self.last_cycle_notes = notes
            self.last_cycle_timestamp = now
            try:
                self._sync_state(db)
            except Exception:
                logger.exception("Failed syncing bot state")
            return notes
        finally:
            db.close()

