from __future__ import annotations

from dataclasses import asdict

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.repositories.signal_repository import SignalRepository
from app.repositories.trade_repository import TradeRepository
from app.services.ai_model import TradeConfidenceModel
from app.services.execution.binance_executor import BinanceExecutor
from app.services.execution.mt5_executor import MT5Executor
from app.services.execution.types import OrderRequest
from app.services.market_data import MarketDataService
from app.services.risk_engine import RiskEngine
from app.services.strategy import LiquidityBOSPullbackStrategy, StrategySignal


class TradingEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.market_data = MarketDataService(settings)
        self.strategy = LiquidityBOSPullbackStrategy()
        self.ai = TradeConfidenceModel()
        self.risk = RiskEngine(
            risk_per_trade=settings.risk_per_trade,
            max_drawdown=settings.max_drawdown,
            max_trades_per_session=settings.max_trades_per_session,
        )
        self.mt5 = MT5Executor(settings)
        self.binance = BinanceExecutor(settings)

    def _signal_features(self, signal: StrategySignal) -> list[float]:
        return [
            signal.sweep_strength,
            signal.bos_strength,
            signal.pullback_quality,
            signal.atr_regime,
            signal.momentum,
        ]

    def run_once(self, db: Session, market: str, symbol: str, timeframe: str) -> dict:
        trade_repo = TradeRepository(db)
        signal_repo = SignalRepository(db)

        frame = self.market_data.get_ohlcv(market=market, symbol=symbol, timeframe=timeframe, bars=350)
        signal = self.strategy.generate_signal(frame)
        if signal is None:
            return {"message": "No valid signal generated", "signal_id": None, "trade_id": None}

        confidence = self.ai.score(self._signal_features(signal))
        signal_record = signal_repo.create_signal(
            market=market,
            symbol=symbol,
            side=signal.side,
            timeframe=timeframe,
            signal_type="liquidity_bos_pullback",
            status="live",
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            tp1=signal.tp1,
            tp2=signal.tp2,
            tp3=signal.tp3,
            confidence=confidence,
            atr_value=signal.atr_value,
            executed=False,
        )

        latest = trade_repo.get_latest_equity()
        if latest is None:
            latest = trade_repo.create_equity_snapshot(balance=10000.0, equity=10000.0, drawdown=0.0)
        peak_equity = max(trade_repo.get_peak_equity(), latest.equity)
        session_count = trade_repo.count_session_trades(self.settings.session_name)

        risk_decision = self.risk.evaluate(
            equity=latest.equity,
            peak_equity=peak_equity,
            session_trade_count=session_count,
            entry=signal.entry_price,
            stop_loss=signal.stop_loss,
        )

        if confidence < 0.55:
            signal_record.status = "filtered_ai"
            db.commit()
            return {"message": "Signal filtered by AI confidence", "signal_id": signal_record.id, "trade_id": None}

        if not risk_decision.allowed:
            signal_record.status = "filtered_risk"
            db.commit()
            return {"message": f"Signal blocked: {risk_decision.reason}", "signal_id": signal_record.id, "trade_id": None}

        order_request = OrderRequest(
            symbol=symbol,
            side=signal.side,
            quantity=risk_decision.quantity,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            tp1=signal.tp1,
            tp2=signal.tp2,
            tp3=signal.tp3,
        )
        execution = self.mt5.execute(order_request) if market.lower() == "forex" else self.binance.execute(order_request)

        trade = trade_repo.create_trade(
            market=market,
            symbol=symbol,
            side=signal.side,
            status="open" if execution.success else "rejected",
            session_name=self.settings.session_name,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            tp1=signal.tp1,
            tp2=signal.tp2,
            tp3=signal.tp3,
            quantity=risk_decision.quantity,
            confidence=confidence,
            risk_percent=self.settings.risk_per_trade,
            atr_value=signal.atr_value,
            pnl=0.0,
        )

        if execution.success:
            signal_record.status = "executed"
            signal_record.executed = True
        else:
            signal_record.status = "execution_failed"
        db.commit()

        drawdown = self.risk.calculate_drawdown(current_equity=latest.equity, peak_equity=peak_equity)
        trade_repo.create_equity_snapshot(balance=latest.balance, equity=latest.equity, drawdown=drawdown)

        return {
            "message": execution.message or "trade processed",
            "signal_id": signal_record.id,
            "trade_id": trade.id,
            "execution": asdict(execution),
        }
