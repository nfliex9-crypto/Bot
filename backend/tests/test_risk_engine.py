from app.services.risk_engine import RiskEngine


def test_position_size_uses_075_percent_risk() -> None:
    engine = RiskEngine(risk_per_trade=0.0075, max_drawdown=0.15, max_trades_per_session=3)
    qty = engine.position_size(equity=10000, entry=1.1050, stop_loss=1.1000)
    # Risk amount = 75. Stop distance = 0.005 => size = 15000 units.
    assert round(qty, 2) == 15000.00


def test_blocks_when_trade_limit_reached() -> None:
    engine = RiskEngine(risk_per_trade=0.0075, max_drawdown=0.15, max_trades_per_session=3)
    decision = engine.evaluate(
        equity=10000,
        peak_equity=10000,
        session_trade_count=3,
        entry=1.2,
        stop_loss=1.19,
    )
    assert decision.allowed is False
    assert "max trades per session" in decision.reason
