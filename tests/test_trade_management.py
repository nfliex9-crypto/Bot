import pytest

from app.trade_management.manager import TradeAction, TradeManager


@pytest.fixture
def tm():
    return TradeManager()


def test_tp1_triggers_partial_close_and_be(tm):
    decisions = tm.evaluate(
        current_price=1.1050,
        side="long",
        entry_price=1.1000,
        stop_loss=1.0950,
        tp1=1.1050,
        tp2=1.1075,
        tp3=1.1100,
    )
    actions = [d.action for d in decisions]
    assert TradeAction.PARTIAL_CLOSE_TP1 in actions
    assert TradeAction.MOVE_TO_BREAKEVEN in actions


def test_stop_loss_triggers_full_close(tm):
    decisions = tm.evaluate(
        current_price=1.0940,
        side="long",
        entry_price=1.1000,
        stop_loss=1.0950,
        tp1=1.1050,
        tp2=1.1075,
        tp3=1.1100,
    )
    actions = [d.action for d in decisions]
    assert TradeAction.STOP_LOSS_HIT in actions
    assert decisions[0].close_pct == 1.0


def test_tp3_closes_full(tm):
    decisions = tm.evaluate(
        current_price=1.1110,
        side="long",
        entry_price=1.1000,
        stop_loss=1.0950,
        tp1=1.1050,
        tp2=1.1075,
        tp3=1.1100,
    )
    actions = [d.action for d in decisions]
    assert TradeAction.CLOSE_TP3 in actions


def test_short_tp1(tm):
    decisions = tm.evaluate(
        current_price=1.0950,
        side="short",
        entry_price=1.1000,
        stop_loss=1.1050,
        tp1=1.0950,
        tp2=1.0925,
        tp3=1.0900,
    )
    actions = [d.action for d in decisions]
    assert TradeAction.PARTIAL_CLOSE_TP1 in actions


def test_no_action_when_in_range(tm):
    decisions = tm.evaluate(
        current_price=1.1020,
        side="long",
        entry_price=1.1000,
        stop_loss=1.0950,
        tp1=1.1050,
        tp2=1.1075,
        tp3=1.1100,
    )
    assert len(decisions) == 0
