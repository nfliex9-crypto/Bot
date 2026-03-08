from app.services.risk import RiskEngine
from app.services.strategy import StrategySignal
from app.db.models import MarketType, OrderSide


def _sample_signal() -> StrategySignal:
    return StrategySignal(
        symbol="EURUSD",
        market=MarketType.FOREX,
        timeframe="M15",
        side=OrderSide.LONG,
        entry_price=1.1050,
        stop_loss=1.1000,
        tp1=1.1100,
        tp2=1.1150,
        tp3=1.1200,
        rationale="Test signal",
        features={"atr_ratio": 0.002, "liquidity_sweep": 1, "bos": 1, "pullback_ratio": 0.5},
    )


def test_risk_engine_approves_valid_trade() -> None:
    engine = RiskEngine()
    decision = engine.evaluate(
        signal=_sample_signal(),
        account_equity=100000.0,
        current_drawdown=0.02,
        session_trade_count=1,
    )

    assert decision.approved is True
    assert decision.risk_amount == 750.0
    assert decision.quantity > 0


def test_risk_engine_rejects_when_trade_cap_reached() -> None:
    engine = RiskEngine()
    decision = engine.evaluate(
        signal=_sample_signal(),
        account_equity=100000.0,
        current_drawdown=0.02,
        session_trade_count=3,
    )

    assert decision.approved is False
    assert "Maximum trades" in decision.reason
