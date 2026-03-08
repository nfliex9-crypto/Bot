from datetime import datetime, timezone

from app.trading.position_manager import ManagedPosition, PositionManager


def test_break_even_after_tp1() -> None:
    manager = PositionManager()
    position = ManagedPosition(
        symbol="EURUSD",
        market="forex",
        side="buy",
        entry=1.1000,
        stop_loss=1.0950,
        take_profits=[1.1050, 1.1075, 1.1100],
        quantity=1.0,
        opened_at=datetime.now(tz=timezone.utc),
    )
    manager.add(position)
    updated = manager.on_price("EURUSD", "forex", 1.1050)
    assert updated is not None
    assert updated.moved_to_be is True
    assert updated.stop_loss == 1.1000
