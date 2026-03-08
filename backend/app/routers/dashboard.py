from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import EquitySnapshot, RecordStatus, Signal, Trade
from app.db.session import get_db
from app.schemas import DashboardOverview, EquitySnapshotResponse, SignalResponse, TradeResponse

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=DashboardOverview)
def get_dashboard_overview(db: Session = Depends(get_db)) -> DashboardOverview:
    latest_equity = db.query(EquitySnapshot).order_by(EquitySnapshot.created_at.desc()).first()
    live_signal_entities = db.query(Signal).order_by(Signal.created_at.desc()).limit(10).all()
    recent_trades = db.query(Trade).order_by(Trade.opened_at.desc()).limit(10).all()

    total_closed = db.query(Trade).filter(Trade.status == RecordStatus.CLOSED).count()
    profitable = db.query(Trade).filter(Trade.status == RecordStatus.CLOSED, Trade.pnl > 0).count()
    total_pnl = db.query(func.coalesce(func.sum(Trade.pnl), 0.0)).scalar() or 0.0
    win_rate = (profitable / total_closed) if total_closed else 0.0

    return DashboardOverview(
        latest_equity=EquitySnapshotResponse.model_validate(latest_equity) if latest_equity else None,
        live_signals=[SignalResponse.model_validate(row) for row in live_signal_entities],
        recent_trades=[TradeResponse.model_validate(row) for row in recent_trades],
        win_rate=round(win_rate, 4),
        total_pnl=round(float(total_pnl), 2),
    )


@router.get("/equity", response_model=list[EquitySnapshotResponse])
def get_equity_curve(db: Session = Depends(get_db)) -> list[EquitySnapshotResponse]:
    rows = db.query(EquitySnapshot).order_by(EquitySnapshot.created_at.asc()).limit(100).all()
    return [EquitySnapshotResponse.model_validate(row) for row in rows]
