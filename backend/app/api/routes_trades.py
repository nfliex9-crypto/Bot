from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.trade_repository import TradeRepository
from app.schemas.trade import TradeListResponse

router = APIRouter(prefix="/trades", tags=["trades"])


@router.get("/history", response_model=TradeListResponse)
def trade_history(db: Session = Depends(get_db)) -> TradeListResponse:
    items = TradeRepository(db).list_recent()
    return TradeListResponse(items=items)


@router.post("/{trade_id}/tp1-hit")
def mark_tp1_hit(trade_id: int, db: Session = Depends(get_db)) -> dict:
    repo = TradeRepository(db)
    trade = repo.get_trade(trade_id)
    if trade is None:
        raise HTTPException(status_code=404, detail="Trade not found")
    trade.stop_loss = trade.entry_price
    db.commit()
    return {"message": "Stop loss moved to break-even", "trade_id": trade_id}
