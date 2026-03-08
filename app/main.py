"""FastAPI application - 24/7 trading bot API."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from config import settings
from app.database.session import init_db, get_db
from app.database.models import Trade
from app.engine import TradingEngine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB on startup."""
    init_db()
    yield
    # Shutdown


app = FastAPI(
    title="AI Automated Trading Bot",
    description="Forex (MT5) + Crypto (Binance) | Liquidity Sweep, BOS, Pullback | 24/7",
    version="1.0.0",
    lifespan=lifespan,
)


class StatusResponse(BaseModel):
    mode: str
    status: str


class TradeResponse(BaseModel):
    id: int
    order_id: str
    symbol: str
    direction: str
    strategy: str
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    size: float
    confidence: float | None
    market_type: str
    paper: bool
    status: str
    created_at: str


@app.get("/", response_model=StatusResponse)
def root():
    return StatusResponse(
        mode=settings.TRADING_MODE,
        status="running",
    )


@app.get("/health")
def health():
    return {"status": "ok", "mode": settings.TRADING_MODE}


@app.get("/trades", response_model=list[TradeResponse])
def list_trades(db: Session = Depends(get_db), limit: int = 50):
    trades = db.query(Trade).order_by(Trade.created_at.desc()).limit(limit).all()
    return [
        TradeResponse(
            id=t.id,
            order_id=t.order_id,
            symbol=t.symbol,
            direction=t.direction,
            strategy=t.strategy,
            entry_price=t.entry_price,
            stop_loss=t.stop_loss,
            tp1=t.tp1, tp2=t.tp2, tp3=t.tp3,
            size=t.size,
            confidence=t.confidence,
            market_type=t.market_type,
            paper=t.paper,
            status=t.status,
            created_at=t.created_at.isoformat() if t.created_at else "",
        )
        for t in trades
    ]


@app.post("/run-cycle")
def run_cycle():
    """Manually trigger one trading cycle."""
    engine = TradingEngine()
    return engine.run_cycle()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.API_HOST, port=settings.API_PORT)
