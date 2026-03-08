from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.models import Trade
from app.db.session import get_db
from app.schemas import TradeResponse

router = APIRouter(prefix="/api/trades", tags=["trades"])


@router.get("/history", response_model=list[TradeResponse])
def get_trade_history(db: Session = Depends(get_db)) -> list[TradeResponse]:
    rows = db.query(Trade).order_by(Trade.opened_at.desc()).limit(50).all()
    return [TradeResponse.model_validate(row) for row in rows]
