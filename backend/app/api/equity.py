from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import User
from app.schemas.schemas import EquitySnapshotResponse
from app.services.auth_service import get_current_user
from app.services.trading_service import TradingService

router = APIRouter(prefix="/equity", tags=["Equity"])


@router.get("/history", response_model=list[EquitySnapshotResponse])
async def get_equity_history(
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get equity curve history."""
    service = TradingService(db)
    snapshots = await service.get_equity_history(current_user.id, limit)
    return snapshots


@router.post("/snapshot", response_model=EquitySnapshotResponse)
async def take_equity_snapshot(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Take a snapshot of current equity."""
    service = TradingService(db)
    snapshot = await service.snapshot_equity(current_user.id)
    return snapshot
