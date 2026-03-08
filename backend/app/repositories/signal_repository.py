from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.signal import Signal


class SignalRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_signal(self, **kwargs) -> Signal:
        signal = Signal(**kwargs)
        self.db.add(signal)
        self.db.commit()
        self.db.refresh(signal)
        return signal

    def list_live(self, limit: int = 100) -> list[Signal]:
        stmt = select(Signal).where(Signal.status == "live").order_by(desc(Signal.created_at)).limit(limit)
        return list(self.db.scalars(stmt).all())
