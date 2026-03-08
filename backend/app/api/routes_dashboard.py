from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.trade_repository import TradeRepository
from app.schemas.dashboard import EquityPoint, EquityResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/equity", response_model=EquityResponse)
def equity_dashboard(db: Session = Depends(get_db)) -> EquityResponse:
    repo = TradeRepository(db)
    latest = repo.get_latest_equity()
    if latest is None:
        latest = repo.create_equity_snapshot(balance=10000.0, equity=10000.0, drawdown=0.0)

    points = [
        EquityPoint(
            timestamp=item.created_at,
            equity=item.equity,
            balance=item.balance,
            drawdown=item.drawdown,
        )
        for item in repo.list_equity_points()
    ]
    return EquityResponse(
        current_equity=latest.equity,
        current_balance=latest.balance,
        max_drawdown=repo.get_max_drawdown(),
        points=points,
    )
