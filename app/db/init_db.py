from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Base, BotState
from app.db.session import engine


def create_database() -> None:
    Base.metadata.create_all(bind=engine)


def ensure_bot_state(session: Session) -> BotState:
    state = session.scalar(select(BotState).where(BotState.id == 1))
    if state is None:
        settings = get_settings()
        state = BotState(
            id=1,
            trading_enabled=True,
            current_equity=settings.account_balance,
            peak_equity=settings.account_balance,
            current_drawdown=0.0,
            open_positions=0,
        )
        session.add(state)
        session.flush()
    return state
