from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.ai.model import AIModelService
from app.core.config import Settings
from app.db.models import EquitySnapshot, Signal, Trade
from app.execution.engine import ExecutionEngine
from app.market.data_provider import MarketDataProvider
from app.risk.engine import RiskEngine
from app.strategy.detector import SmartMoneyStrategy


class TradingService:
    def __init__(
        self,
        settings: Settings,
        strategy: SmartMoneyStrategy,
        risk_engine: RiskEngine,
        ai_service: AIModelService,
        execution_engine: ExecutionEngine,
        market_data: MarketDataProvider,
    ):
        self.settings = settings
        self.strategy = strategy
        self.risk_engine = risk_engine
        self.ai_service = ai_service
        self.execution_engine = execution_engine
        self.market_data = market_data

    def _session_id(self) -> str:
        return datetime.utcnow().strftime("%Y%m%d")

    def _equity_context(self, db: Session, session_id: str) -> tuple[float, float]:
        realized_pnl = (
            db.query(Trade)
            .filter(Trade.status.in_(["CLOSED", "PAPER_CLOSED"]))
            .with_entities(Trade.pnl)
            .all()
        )
        equity = self.settings.initial_equity + sum(row[0] for row in realized_pnl)

        peak = db.query(EquitySnapshot).order_by(desc(EquitySnapshot.equity)).first()
        peak_equity = peak.equity if peak else self.settings.initial_equity
        drawdown = max((peak_equity - equity) / max(peak_equity, 1e-8), 0.0)

        snapshot = EquitySnapshot(equity=equity, drawdown=drawdown, session_id=session_id)
        db.add(snapshot)
        db.commit()

        return float(equity), float(drawdown)

    def _session_trade_count(self, db: Session, session_id: str) -> int:
        return db.query(Trade).filter(Trade.session_id == session_id).count()

    def _get_market_price(self, market: str, symbol: str) -> float | None:
        candles = (
            self.market_data.get_forex_candles(symbol, limit=50)
            if market == "FOREX"
            else self.market_data.get_crypto_candles(symbol, limit=50)
        )
        if candles.empty:
            return None
        return float(candles["close"].iloc[-1])

    def _close_pnl(self, side: str, entry_price: float, current_price: float, quantity: float) -> float:
        if side == "BUY":
            return float((current_price - entry_price) * quantity)
        return float((entry_price - current_price) * quantity)

    def _manage_open_trades(self, db: Session) -> None:
        open_rows = db.query(Trade).filter(Trade.status.in_(["OPEN", "PAPER"])).all()

        for trade in open_rows:
            current_price = self._get_market_price(trade.market, trade.symbol)
            if current_price is None:
                continue

            new_stop = self.risk_engine.break_even_stop(
                side=trade.side,
                entry_price=trade.entry_price,
                current_stop=trade.stop_loss,
                current_price=current_price,
                tp1=trade.tp1,
            )

            if new_stop != trade.stop_loss:
                trade.stop_loss = new_stop
                metadata = dict(trade.metadata_json or {})
                metadata["moved_to_break_even"] = True
                metadata["break_even_price"] = trade.entry_price
                trade.metadata_json = metadata

            tp3_hit = current_price >= trade.tp3 if trade.side == "BUY" else current_price <= trade.tp3
            sl_hit = current_price <= trade.stop_loss if trade.side == "BUY" else current_price >= trade.stop_loss
            if tp3_hit or sl_hit:
                trade.pnl = self._close_pnl(trade.side, trade.entry_price, current_price, trade.quantity)
                trade.status = "CLOSED" if trade.status == "OPEN" else "PAPER_CLOSED"
                trade.closed_at = datetime.utcnow()

            db.add(trade)

        db.commit()

    def run_cycle(self, db: Session) -> dict:
        self._manage_open_trades(db)
        session_id = self._session_id()
        account_equity, drawdown = self._equity_context(db, session_id)
        trade_count = self._session_trade_count(db, session_id)

        can_trade, reason = self.risk_engine.can_trade(trade_count, drawdown)
        if not can_trade:
            return {"ok": True, "trades_opened": 0, "signals": 0, "reason": reason}

        total_signals = 0
        total_trades = 0

        market_symbol_map = {
            "FOREX": self.settings.forex_symbol_list,
            "CRYPTO": self.settings.crypto_symbol_list,
        }

        for market, symbols in market_symbol_map.items():
            for symbol in symbols:
                candles = (
                    self.market_data.get_forex_candles(symbol)
                    if market == "FOREX"
                    else self.market_data.get_crypto_candles(symbol)
                )
                signal = self.strategy.generate_signal(market=market, symbol=symbol, df=candles)
                if signal is None:
                    continue

                confidence = self.ai_service.predict_confidence(signal.features, signal.strategy_score)
                total_signals += 1

                signal_row = Signal(
                    market=signal.market,
                    symbol=signal.symbol,
                    side=signal.side,
                    confidence=confidence,
                    strategy_score=signal.strategy_score,
                    features=signal.features,
                    reason=signal.reason,
                    executed=False,
                )
                db.add(signal_row)
                db.commit()
                db.refresh(signal_row)

                if confidence < self.settings.ai_confidence_threshold:
                    continue

                if self._session_trade_count(db, session_id) >= self.settings.max_trades_per_session:
                    continue

                plan = self.risk_engine.build_trade_plan(
                    side=signal.side,
                    entry_price=signal.entry_price,
                    account_equity=account_equity,
                    candles=candles,
                )

                execution_result = self.execution_engine.execute(
                    market=market,
                    symbol=symbol,
                    side=signal.side,
                    quantity=plan.quantity,
                    stop_loss=plan.stop_loss,
                    tp1=plan.tp1,
                )

                executed = execution_result.executed if self.settings.trading_enabled else False
                signal_row.executed = executed
                db.add(signal_row)

                trade_row = Trade(
                    market=market,
                    symbol=symbol,
                    side=signal.side,
                    quantity=plan.quantity,
                    entry_price=signal.entry_price,
                    stop_loss=plan.stop_loss,
                    tp1=plan.tp1,
                    tp2=plan.tp2,
                    tp3=plan.tp3,
                    confidence=confidence,
                    risk_amount=plan.risk_amount,
                    status="OPEN" if executed else "PAPER",
                    broker_order_id=execution_result.order_id,
                    session_id=session_id,
                    metadata_json={
                        "execution_reason": execution_result.reason,
                        "simulated": execution_result.simulated or not self.settings.trading_enabled,
                        "break_even_after_tp1": True,
                        "features": signal.features,
                    },
                )

                db.add(trade_row)
                db.commit()

                total_trades += 1

        return {
            "ok": True,
            "session_id": session_id,
            "signals": total_signals,
            "trades_opened": total_trades,
            "drawdown": drawdown,
        }

    def train_ai_model(self, db: Session) -> dict:
        closed = db.query(Trade).filter(Trade.status.in_(["CLOSED", "PAPER_CLOSED"]))

        rows: list[dict] = []
        for trade in closed:
            feat = trade.metadata_json.get("features") if trade.metadata_json else None
            if not feat:
                continue
            rows.append({"features": feat, "label": 1 if trade.pnl > 0 else 0})

        return self.ai_service.train(rows)
