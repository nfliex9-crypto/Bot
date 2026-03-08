from datetime import UTC, datetime

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.equity_snapshot import EquitySnapshot
from app.models.trade import Trade


class TradeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_trade(self, **kwargs) -> Trade:
        trade = Trade(**kwargs)
        self.db.add(trade)
        self.db.commit()
        self.db.refresh(trade)
        return trade

    def list_recent(self, limit: int = 100) -> list[Trade]:
        stmt = select(Trade).order_by(desc(Trade.opened_at)).limit(limit)
        return list(self.db.scalars(stmt).all())

    def get_trade(self, trade_id: int) -> Trade | None:
        stmt = select(Trade).where(Trade.id == trade_id)
        return self.db.scalars(stmt).first()

    def count_session_trades(self, session_name: str) -> int:
        day_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = select(func.count(Trade.id)).where(
            Trade.session_name == session_name,
            Trade.opened_at >= day_start,
        )
        return int(self.db.execute(stmt).scalar_one())

    def create_equity_snapshot(self, balance: float, equity: float, drawdown: float) -> EquitySnapshot:
        snapshot = EquitySnapshot(balance=balance, equity=equity, drawdown=drawdown)
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    def list_equity_points(self, limit: int = 200) -> list[EquitySnapshot]:
        stmt = select(EquitySnapshot).order_by(desc(EquitySnapshot.created_at)).limit(limit)
        return list(reversed(list(self.db.scalars(stmt).all())))

    def get_latest_equity(self) -> EquitySnapshot | None:
        stmt = select(EquitySnapshot).order_by(desc(EquitySnapshot.created_at)).limit(1)
        return self.db.scalars(stmt).first()

    def get_max_drawdown(self) -> float:
        stmt = select(func.max(EquitySnapshot.drawdown))
        result = self.db.execute(stmt).scalar_one_or_none()
        return float(result or 0.0)

    def get_peak_equity(self) -> float:
        stmt = select(func.max(EquitySnapshot.equity))
        result = self.db.execute(stmt).scalar_one_or_none()
        return float(result or 0.0)
