from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_trading_engine
from app.core.database import get_db
from app.repositories.signal_repository import SignalRepository
from app.schemas.signal import RunSignalRequest, RunSignalResponse, SignalListResponse
from app.services.trading_engine import TradingEngine

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("/live", response_model=SignalListResponse)
def list_live_signals(db: Session = Depends(get_db)) -> SignalListResponse:
    items = SignalRepository(db).list_live()
    return SignalListResponse(items=items)


@router.post("/run-once", response_model=RunSignalResponse)
def run_engine_once(
    payload: RunSignalRequest,
    db: Session = Depends(get_db),
    engine: TradingEngine = Depends(get_trading_engine),
) -> RunSignalResponse:
    result = engine.run_once(db, payload.market, payload.symbol, payload.timeframe)
    return RunSignalResponse(**{k: result.get(k) for k in ("message", "signal_id", "trade_id")})
