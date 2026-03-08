from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import User
from app.schemas.schemas import AIModelMetricsResponse, TrainModelRequest
from app.services.auth_service import get_current_user
from app.services.trading_service import TradingService

router = APIRouter(prefix="/ai", tags=["AI Model"])


@router.post("/train", response_model=AIModelMetricsResponse)
async def train_model(
    request: TrainModelRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Train the AI classifier on historical data."""
    service = TradingService(db)
    metrics = await service.engine.train_ai_model(request.symbol, request.timeframe)
    return metrics


@router.get("/metrics", response_model=AIModelMetricsResponse)
async def get_model_metrics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current AI model performance metrics."""
    service = TradingService(db)
    return {
        "model_version": service.engine.classifier.model_version,
        **service.engine.classifier.metrics,
    }


@router.get("/feature-importance")
async def get_feature_importance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get feature importance rankings from the AI model."""
    service = TradingService(db)
    importance = service.engine.classifier.get_feature_importance()
    return {"features": importance}


@router.post("/predict")
async def predict_confidence(
    symbol: str = "EURUSD",
    timeframe: str = "H1",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get AI confidence prediction for a symbol."""
    service = TradingService(db)
    connector = (
        service.engine.mt5
        if symbol in service.engine.FOREX_SYMBOLS
        else service.engine.binance
    )
    df = await connector.get_ohlcv(symbol, timeframe, 500)
    if df.empty:
        return {"confidence": 0.5, "error": "No data available"}

    confidence = service.engine.classifier.predict_confidence(df)
    return {"symbol": symbol, "timeframe": timeframe, "confidence": confidence}
