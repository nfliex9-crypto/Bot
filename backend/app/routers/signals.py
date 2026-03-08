from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.models import Signal
from app.db.session import get_db
from app.schemas import RunCycleResponse, SignalResponse
from app.services.orchestrator import TradingOrchestrator

router = APIRouter(prefix="/api/signals", tags=["signals"])
orchestrator = TradingOrchestrator()


@router.get("/live", response_model=list[SignalResponse])
def get_live_signals(db: Session = Depends(get_db)) -> list[SignalResponse]:
    rows = db.query(Signal).order_by(Signal.created_at.desc()).limit(25).all()
    return [SignalResponse.model_validate(row) for row in rows]


@router.post("/run-cycle", response_model=RunCycleResponse)
def run_trading_cycle(db: Session = Depends(get_db)) -> RunCycleResponse:
    result = orchestrator.run_cycle(db)
    return RunCycleResponse(**result)
