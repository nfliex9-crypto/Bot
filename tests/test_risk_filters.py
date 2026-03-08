from __future__ import annotations

from datetime import datetime, timedelta, timezone

from trading_bot.config import Settings
from trading_bot.domain import InstrumentSpec, MarketType, NewsEvent, TradeDirection, TradeSignal
from trading_bot.filters import HighImpactNewsFilter, SessionFilter
from trading_bot.risk import RiskManager


def build_signal() -> TradeSignal:
    return TradeSignal(
        symbol="EURUSD",
        market=MarketType.FOREX,
        direction=TradeDirection.LONG,
        entry_price=1.1050,
        stop_loss=1.1025,
        take_profit_levels=[1.1075, 1.10875, 1.1100],
        reason="test",
        confidence=0.7,
        atr=0.0010,
        pullback_level=1.1040,
        bos_level=1.1048,
        liquidity_level=1.1028,
        h1_bias="bullish",
        m15_trend="bullish",
        session="london",
        features={
            "atr": 0.0010,
            "risk_distance": 0.0025,
            "bos_displacement": 0.0002,
            "pullback_depth": 0.0010,
            "liquidity_distance": 0.0022,
            "h1_alignment": 1.0,
            "m15_alignment": 1.0,
            "session_score": 1.0,
        },
    )


def test_risk_manager_builds_position_plan() -> None:
    settings = Settings(stop_method="structure")
    manager = RiskManager(settings)
    spec = InstrumentSpec(
        symbol="EURUSD",
        market=MarketType.FOREX,
        quantity_step=0.01,
        min_quantity=0.01,
        tick_size=0.0001,
        point_value=100000.0,
    )

    plan = manager.build_position_plan(build_signal(), spec)

    assert round(plan.risk_amount, 2) == 22.50
    assert plan.quantity >= 0.01
    assert plan.take_profit_levels[0] > plan.entry_price


def test_risk_manager_blocks_when_drawdown_limit_hit() -> None:
    settings = Settings()
    manager = RiskManager(settings)
    result = manager.can_open_trade(
        session_trade_count=0,
        open_positions=0,
        realized_pnls=[-500.0],
    )
    assert result.allowed is False


def test_session_filter_allows_london_only() -> None:
    settings = Settings()
    session_filter = SessionFilter(settings)
    london_time = datetime(2026, 1, 5, 8, 0, tzinfo=timezone.utc)
    asia_time = datetime(2026, 1, 5, 2, 0, tzinfo=timezone.utc)

    assert session_filter.active_session(london_time) == "london"
    assert session_filter.active_session(asia_time) is None


def test_news_filter_blocks_high_impact_event() -> None:
    settings = Settings(news_block_window_minutes=30)
    news_filter = HighImpactNewsFilter(settings)
    now = datetime.now(timezone.utc)
    events = [
        NewsEvent(
            title="US CPI",
            currency="USD",
            impact="high",
            starts_at=now + timedelta(minutes=10),
            source="test",
        )
    ]

    assert news_filter.is_blocked(
        market=MarketType.FOREX,
        symbol="EURUSD",
        now=now,
        events=events,
    )
