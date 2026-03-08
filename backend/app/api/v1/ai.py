from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any

from app.database import get_db
from app.ai.classifier import TradingClassifier
from app.config import settings

router = APIRouter(prefix="/ai", tags=["AI"])

# Singleton classifier
_classifier: TradingClassifier = None


def get_classifier() -> TradingClassifier:
    global _classifier
    if _classifier is None:
        _classifier = TradingClassifier(model_path=settings.MODEL_PATH)
    return _classifier


@router.get("/model/info")
async def get_model_info():
    """Return metadata about the current AI model."""
    clf = get_classifier()
    return clf.get_model_info()


@router.post("/model/retrain")
async def retrain_model(db: AsyncSession = Depends(get_db)):
    """
    Trigger model retraining from historical trade data.
    Returns a training report.
    """
    from app.models.trade import Trade, TradeStatus
    import numpy as np

    clf = get_classifier()

    stmt = select(Trade).where(Trade.status == TradeStatus.CLOSED)
    result = await db.execute(stmt)
    trades = result.scalars().all()

    if len(trades) < 50:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least 50 closed trades for retraining (have {len(trades)})"
        )

    # Bootstrap: use confidence score as proxy feature for historical data
    X = []
    y = []
    for t in trades:
        if t.confidence_score is not None:
            features = [t.confidence_score] + [0.0] * (len(clf.feature_names) - 1)
            X.append(features)
            y.append(1 if (t.pnl or 0) > 0 else 0)

    if len(X) < 50:
        raise HTTPException(status_code=400, detail="Insufficient feature data for retraining")

    import numpy as np
    report = clf.train(np.array(X, dtype=np.float32), np.array(y), save=True)
    return report


@router.get("/confidence/history")
async def get_confidence_history(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Return AI confidence scores over recent signals."""
    from app.models.signal import Signal
    from sqlalchemy import desc

    stmt = (
        select(Signal.id, Signal.symbol, Signal.direction,
               Signal.confidence_score, Signal.created_at, Signal.status)
        .where(Signal.confidence_score.isnot(None))
        .order_by(desc(Signal.created_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        {
            "signal_id": r.id,
            "symbol": r.symbol,
            "direction": r.direction,
            "confidence": r.confidence_score,
            "timestamp": r.created_at.isoformat() if r.created_at else None,
            "status": r.status.value if r.status else None,
        }
        for r in rows
    ]
