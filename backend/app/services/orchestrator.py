from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import EquitySnapshot, MarketType, RecordStatus, Signal, Trade
from app.services.ai import TradeAIService
from app.services.execution import ExecutionService
from app.services.market_data import MarketDataService
from app.services.risk import RiskEngine
from app.services.strategy import SmartMoneyStrategy

logger = logging.getLogger(__name__)
settings = get_settings()


class TradingOrchestrator:
    def __init__(self) -> None:
        self.market_data = MarketDataService()
        self.strategy = SmartMoneyStrategy()
        self.ai = TradeAIService()
        self.risk = RiskEngine()
        self.execution = ExecutionService()

    def run_cycle(self, db: Session) -> dict[str, int]:
        self._ensure_equity_snapshot(db)
        summary = {
            "processed_symbols": 0,
            "generated_signals": 0,
            "executed_trades": 0,
            "rejected_trades": 0,
        }

        for market, symbols in (
            (MarketType.FOREX, settings.forex_symbol_list),
            (MarketType.CRYPTO, settings.crypto_symbol_list),
        ):
            for symbol in symbols:
                summary["processed_symbols"] += 1
                df = self.market_data.get_ohlcv(symbol, market, settings.default_timeframe, settings.candle_limit)
                if df.empty:
                    continue

                self._manage_open_trades(db, symbol, market, df)

                candidate = self.strategy.analyze(symbol, market, settings.default_timeframe, df)
                if candidate is None:
                    continue

                summary["generated_signals"] += 1
                ai_score = self.ai.score_signal(db, candidate)
                confidence = ai_score.confidence

                signal = Signal(
                    symbol=candidate.symbol,
                    market=candidate.market,
                    timeframe=candidate.timeframe,
                    side=candidate.side,
                    confidence=confidence,
                    entry_price=candidate.entry_price,
                    stop_loss=candidate.stop_loss,
                    tp1=candidate.tp1,
                    tp2=candidate.tp2,
                    tp3=candidate.tp3,
                    status=RecordStatus.PENDING,
                    rationale=f"{candidate.rationale} Confidence source: {ai_score.source}.",
                    features=candidate.features,
                )
                db.add(signal)
                db.flush()

                if confidence < settings.min_confidence_threshold:
                    signal.status = RecordStatus.REJECTED
                    summary["rejected_trades"] += 1
                    continue

                latest_equity = self._latest_equity(db)
                current_drawdown = self._current_drawdown(db)
                session_trade_count = self._session_trade_count(db)

                decision = self.risk.evaluate(
                    signal=candidate,
                    account_equity=latest_equity.equity if latest_equity else settings.default_account_equity,
                    current_drawdown=current_drawdown,
                    session_trade_count=session_trade_count,
                )

                if not decision.approved:
                    signal.status = RecordStatus.REJECTED
                    signal.rationale = f"{signal.rationale} Risk engine rejected trade: {decision.reason}"
                    summary["rejected_trades"] += 1
                    continue

                trade = Trade(
                    signal_id=signal.id,
                    symbol=candidate.symbol,
                    market=candidate.market,
                    side=candidate.side,
                    quantity=decision.quantity,
                    risk_amount=decision.risk_amount,
                    entry_price=candidate.entry_price,
                    stop_loss=decision.stop_loss,
                    tp1=decision.tp1,
                    tp2=decision.tp2,
                    tp3=decision.tp3,
                    confidence=confidence,
                    broker="paper",
                    status=RecordStatus.PENDING,
                    pnl=0.0,
                    session_name=decision.session_name,
                    meta={"ai_source": ai_score.source, "features": candidate.features},
                )
                db.add(trade)
                db.flush()

                result = self.execution.execute_trade(trade)
                trade.status = result.status
                trade.execution_id = result.execution_id
                trade.broker = result.broker
                trade.meta = {**trade.meta, "execution": result.details}
                signal.status = result.status

                summary["executed_trades"] += 1

        self._record_equity_snapshot(db)
        db.commit()
        return summary

    def _manage_open_trades(self, db: Session, symbol: str, market: MarketType, df) -> None:
        open_trades = (
            db.query(Trade)
            .filter(
                Trade.symbol == symbol,
                Trade.market == market,
                Trade.status.in_([RecordStatus.OPEN, RecordStatus.SIMULATED]),
            )
            .all()
        )
        if not open_trades:
            return

        latest = df.iloc[-1]
        high = float(latest["high"])
        low = float(latest["low"])
        close = float(latest["close"])

        for trade in open_trades:
            trigger_price = high if trade.side.value == "long" else low
            if self.risk.mark_break_even(trade, trigger_price):
                execution_result = self.execution.move_stop_to_break_even(trade)
                trade.meta = {**trade.meta, "break_even": execution_result.details}

            if trade.side.value == "long":
                trade.pnl = (close - trade.entry_price) * trade.quantity
                if high >= trade.tp2:
                    trade.highest_tp_hit = max(trade.highest_tp_hit, 2)
                if high >= trade.tp3:
                    trade.highest_tp_hit = 3
                    self._close_trade(trade, trade.tp3)
                elif low <= trade.stop_loss:
                    self._close_trade(trade, trade.stop_loss)
            else:
                trade.pnl = (trade.entry_price - close) * trade.quantity
                if low <= trade.tp2:
                    trade.highest_tp_hit = max(trade.highest_tp_hit, 2)
                if low <= trade.tp3:
                    trade.highest_tp_hit = 3
                    self._close_trade(trade, trade.tp3)
                elif high >= trade.stop_loss:
                    self._close_trade(trade, trade.stop_loss)

    def _close_trade(self, trade: Trade, exit_price: float) -> None:
        trade.status = RecordStatus.CLOSED
        trade.closed_at = datetime.utcnow()
        if trade.side.value == "long":
            trade.pnl = (exit_price - trade.entry_price) * trade.quantity
        else:
            trade.pnl = (trade.entry_price - exit_price) * trade.quantity

    def _ensure_equity_snapshot(self, db: Session) -> None:
        if db.query(EquitySnapshot).count() > 0:
            return

        snapshot = EquitySnapshot(
            balance=settings.default_account_equity,
            equity=settings.default_account_equity,
            drawdown=0.0,
            open_risk=0.0,
        )
        db.add(snapshot)
        db.commit()

    def _record_equity_snapshot(self, db: Session) -> None:
        starting_balance = settings.default_account_equity
        closed_pnl = db.query(func.coalesce(func.sum(Trade.pnl), 0.0)).filter(Trade.status == RecordStatus.CLOSED).scalar() or 0.0
        open_pnl = (
            db.query(func.coalesce(func.sum(Trade.pnl), 0.0))
            .filter(Trade.status.in_([RecordStatus.OPEN, RecordStatus.SIMULATED]))
            .scalar()
            or 0.0
        )
        open_risk = (
            db.query(func.coalesce(func.sum(Trade.risk_amount), 0.0))
            .filter(Trade.status.in_([RecordStatus.OPEN, RecordStatus.SIMULATED]))
            .scalar()
            or 0.0
        )

        balance = starting_balance + closed_pnl
        equity = balance + open_pnl
        peak_equity = db.query(func.max(EquitySnapshot.equity)).scalar() or balance
        drawdown = max(0.0, (peak_equity - equity) / peak_equity) if peak_equity else 0.0

        db.add(
            EquitySnapshot(
                balance=round(balance, 2),
                equity=round(equity, 2),
                drawdown=round(drawdown, 4),
                open_risk=round(open_risk, 2),
            )
        )

    def _latest_equity(self, db: Session) -> EquitySnapshot | None:
        return db.query(EquitySnapshot).order_by(EquitySnapshot.created_at.desc()).first()

    def _current_drawdown(self, db: Session) -> float:
        latest = self._latest_equity(db)
        if latest is None:
            return 0.0
        return float(latest.drawdown)

    def _session_trade_count(self, db: Session) -> int:
        start, end = self.risk.current_session_bounds()
        return (
            db.query(Trade)
            .filter(
                Trade.opened_at >= start,
                Trade.opened_at < end,
                Trade.status.in_([RecordStatus.OPEN, RecordStatus.CLOSED, RecordStatus.SIMULATED]),
            )
            .count()
        )
