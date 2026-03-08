from __future__ import annotations

import asyncio

from fastapi import Depends, FastAPI, HTTPException, WebSocket
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine, get_db
from app.schemas import DashboardPayload, MarketRequest, TradeRecordOut
from app.services.trading_service import TradingService

settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0")
service = TradingService()


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(f"{settings.api_prefix}/trade/run")
def run_trade_cycle(req: MarketRequest, db: Session = Depends(get_db)):
    return service.run_cycle(req, db)


@app.get(f"{settings.api_prefix}/trades", response_model=list[TradeRecordOut])
def get_trades(limit: int = 100, db: Session = Depends(get_db)):
    return service.list_trades(db, limit=limit)


@app.post(f"{settings.api_prefix}/trades/{{trade_id}}/tp1-hit", response_model=TradeRecordOut)
def mark_tp1(trade_id: int, db: Session = Depends(get_db)):
    trade = service.mark_tp1_and_break_even(db, trade_id=trade_id)
    if trade is None:
        raise HTTPException(status_code=404, detail="trade not found")
    return trade


@app.get(f"{settings.api_prefix}/dashboard", response_model=DashboardPayload)
def dashboard(db: Session = Depends(get_db)):
    history = service.list_trades(db, limit=100)
    equity = service.equity_curve(db)
    return DashboardPayload(
        equity=equity,
        trade_history=history,
        ai_confidence=service.last_confidence,
        live_signal=service.last_signal,
    )


@app.websocket("/ws/signals")
async def signal_stream(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            await ws.send_json(
                {
                    "direction": service.last_signal.direction,
                    "liquidity_sweep": service.last_signal.liquidity_sweep,
                    "break_of_structure": service.last_signal.break_of_structure,
                    "pullback_entry": service.last_signal.pullback_entry,
                    "reason": service.last_signal.reason,
                    "confidence": service.last_confidence,
                }
            )
            await asyncio.sleep(2)
    except Exception:
        await ws.close()


@app.get(f"{settings.api_prefix}/risk/config")
def risk_config():
    return {
        "risk_per_trade": settings.risk_per_trade,
        "max_drawdown": settings.max_drawdown,
        "max_trades_per_session": settings.max_trades_per_session,
        "atr_multiplier": settings.atr_multiplier,
        "tp_multipliers": settings.tp_multipliers,
    }


@app.get(f"{settings.api_prefix}/metrics/equity")
def equity_metrics(db: Session = Depends(get_db)):
    curve = service.equity_curve(db)
    peak = max([x["equity"] for x in curve]) if curve else 0
    current = curve[-1]["equity"] if curve else 0
    drawdown = ((peak - current) / peak) if peak > 0 else 0
    return {"equity_curve": curve, "current_equity": current, "drawdown": drawdown}
