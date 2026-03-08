from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import User
from app.schemas.schemas import (
    SignalResponse, TradeResponse, ExecuteSignalRequest,
    ExecutionResponse, DashboardResponse, RiskStatusResponse,
)
from app.services.auth_service import get_current_user
from app.services.trading_service import TradingService

router = APIRouter(prefix="/trading", tags=["Trading"])


@router.get("/signals", response_model=list[SignalResponse])
async def scan_signals(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Scan all markets for trade signals."""
    service = TradingService(db)
    signals = await service.scan_and_signal(current_user.id)
    return signals


@router.post("/execute", response_model=ExecutionResponse)
async def execute_trade(
    request: ExecuteSignalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Execute a trade signal."""
    service = TradingService(db)
    signal = request.model_dump()
    signal["direction"] = "long" if request.direction == "buy" else request.direction
    result = await service.execute_trade(current_user.id, signal)
    return result


@router.get("/trades", response_model=list[TradeResponse])
async def get_trades(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get trade history."""
    service = TradingService(db)
    trades = await service.get_trade_history(current_user.id, limit, offset)
    return trades


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get dashboard data including equity, risk status, and active trades."""
    service = TradingService(db)
    return await service.engine.get_dashboard_data()


@router.get("/risk-status", response_model=RiskStatusResponse)
async def get_risk_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current risk management status."""
    service = TradingService(db)
    dashboard = await service.engine.get_dashboard_data()
    return dashboard["risk_status"]


@router.post("/auto-trade/start")
async def start_auto_trading(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start automated trading."""
    service = TradingService(db)
    import asyncio
    asyncio.create_task(service.engine.start_auto_trading())
    return {"status": "Auto trading started"}


@router.post("/auto-trade/stop")
async def stop_auto_trading(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stop automated trading."""
    service = TradingService(db)
    await service.engine.stop_auto_trading()
    return {"status": "Auto trading stopped"}


@router.post("/session/reset")
async def reset_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reset trading session counters."""
    service = TradingService(db)
    service.engine.risk_manager.reset_session()
    return {"status": "Session reset"}
