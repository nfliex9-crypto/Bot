from __future__ import annotations

from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session

from app.ai.model import TradeConfidenceModel
from app.core.config import get_settings
from app.db.models import TradeRecord
from app.execution.binance_executor import BinanceExecutionEngine
from app.execution.mt5_executor import MT5ExecutionEngine
from app.risk.engine import RiskEngine
from app.schemas import MarketRequest, Signal, TradeDecision
from app.strategy.market_data import CryptoDataProvider, ForexDataProvider
from app.strategy.signals import build_signal

settings = get_settings()


class TradingService:
    def __init__(self) -> None:
        self.forex_provider = ForexDataProvider()
        self.crypto_provider = CryptoDataProvider()
        self.risk_engine = RiskEngine()
        self.ai_model = TradeConfidenceModel()
        self.mt5_executor = MT5ExecutionEngine()
        self.binance_executor = BinanceExecutionEngine()
        self.last_signal = Signal(
            direction="none",
            liquidity_sweep=False,
            break_of_structure=False,
            pullback_entry=False,
            reason="service initialized",
        )
        self.last_confidence = 0.5

    def _fetch_data(self, req: MarketRequest) -> pd.DataFrame:
        if req.market == "forex":
            return self.forex_provider.get_bars(req.symbol, req.timeframe, req.bars)
        return self.crypto_provider.get_bars(req.symbol, req.timeframe, req.bars)

    def run_cycle(self, req: MarketRequest, db: Session) -> TradeDecision:
        df = self._fetch_data(req)
        signal = build_signal(df)
        confidence = self.ai_model.confidence(df)
        self.last_signal = signal
        self.last_confidence = confidence

        risk_plan = self.risk_engine.build_risk_plan(
            session_id=req.session_id, signal=signal, df=df, equity=req.equity
        )
        if confidence < settings.confidence_threshold:
            risk_plan.allowed = False
            risk_plan.reason = "confidence below threshold"

        if risk_plan.allowed:
            if req.market == "forex":
                _ = self.mt5_executor.place_order(
                    symbol=req.symbol,
                    side=signal.direction,
                    volume=risk_plan.position_size,
                    price=risk_plan.entry_price,
                    stop_loss=risk_plan.stop_loss,
                    take_profit=risk_plan.tp1,
                )
            else:
                _ = self.binance_executor.place_order(
                    symbol=req.symbol,
                    side=signal.direction,
                    quantity=risk_plan.position_size,
                )

            trade = TradeRecord(
                market=req.market,
                symbol=req.symbol,
                side=signal.direction,
                entry_price=risk_plan.entry_price,
                stop_loss=risk_plan.stop_loss,
                tp1=risk_plan.tp1,
                tp2=risk_plan.tp2,
                tp3=risk_plan.tp3,
                position_size=risk_plan.position_size,
                confidence=confidence,
                strategy_reason=signal.reason,
                status="open",
            )
            db.add(trade)
            db.commit()
            self.risk_engine.register_trade(req.session_id)

        return TradeDecision(signal=signal, confidence=confidence, risk_plan=risk_plan)

    @staticmethod
    def list_trades(db: Session, limit: int = 100) -> list[TradeRecord]:
        return (
            db.query(TradeRecord).order_by(TradeRecord.created_at.desc()).limit(limit).all()
        )

    @staticmethod
    def mark_tp1_and_break_even(db: Session, trade_id: int) -> TradeRecord | None:
        trade = db.query(TradeRecord).filter(TradeRecord.id == trade_id).first()
        if trade is None:
            return None
        trade.tp1_hit = True
        trade.break_even_moved = True
        trade.stop_loss = trade.entry_price
        trade.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(trade)
        return trade

    @staticmethod
    def equity_curve(db: Session, base_equity: float = 10000.0) -> list[dict]:
        trades = (
            db.query(TradeRecord)
            .order_by(TradeRecord.created_at.asc())
            .limit(500)
            .all()
        )
        equity = base_equity
        points = [{"timestamp": datetime.utcnow(), "equity": equity}]
        for trade in trades:
            equity += trade.pnl
            points.append({"timestamp": trade.created_at, "equity": equity})
        return points
