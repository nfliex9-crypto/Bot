from fastapi import APIRouter
from app.api.v1 import trades, signals, account, ai

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(trades.router)
api_router.include_router(signals.router)
api_router.include_router(account.router)
api_router.include_router(ai.router)
