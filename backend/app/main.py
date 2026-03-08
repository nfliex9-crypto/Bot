import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.ai.model import AIModelService
from app.core.config import get_settings
from app.db.base import Base
from app.db.models import EquitySnapshot, Signal, Trade
from app.db.schemas import EquityOut, SignalOut, TradeOut
from app.db.session import engine, get_db
from app.execution.engine import ExecutionEngine
from app.market.binance_client import BinanceMarketClient
from app.market.data_provider import MarketDataProvider
from app.market.mt5_client import MT5Client
from app.risk.engine import RiskEngine
from app.services.trading_service import TradingService
from app.strategy.detector import SmartMoneyStrategy

settings = get_settings()

trading_service: TradingService | None = None
trading_task: asyncio.Task | None = None


async def trading_loop():
    while True:
        db = next(get_db())
        try:
            if trading_service is not None:
                trading_service.run_cycle(db)
        finally:
            db.close()
        await asyncio.sleep(settings.trade_loop_seconds)


@asynccontextmanager
async def lifespan(_: FastAPI):
    global trading_service, trading_task

    Base.metadata.create_all(bind=engine)

    mt5 = MT5Client(settings.mt5_login, settings.mt5_password, settings.mt5_server, settings.mt5_path)
    binance = BinanceMarketClient(settings.binance_api_key, settings.binance_api_secret, settings.binance_testnet)

    trading_service = TradingService(
        settings=settings,
        strategy=SmartMoneyStrategy(),
        risk_engine=RiskEngine(
            risk_per_trade=settings.risk_per_trade,
            max_drawdown=settings.max_drawdown,
            max_trades_per_session=settings.max_trades_per_session,
            atr_period=settings.atr_period,
        ),
        ai_service=AIModelService(settings.model_path),
        execution_engine=ExecutionEngine(mt5, binance),
        market_data=MarketDataProvider(mt5, binance),
    )

    trading_task = asyncio.create_task(trading_loop())
    try:
        yield
    finally:
        if trading_task:
            trading_task.cancel()


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.app_name}


@app.post("/trading/cycle")
def run_trading_cycle(db: Session = Depends(get_db)) -> dict:
    assert trading_service is not None
    return trading_service.run_cycle(db)


@app.post("/ai/train")
def train_model(db: Session = Depends(get_db)) -> dict:
    assert trading_service is not None
    return trading_service.train_ai_model(db)


@app.get("/dashboard/equity", response_model=list[EquityOut])
def get_equity(db: Session = Depends(get_db)) -> list[EquitySnapshot]:
    return db.query(EquitySnapshot).order_by(desc(EquitySnapshot.created_at)).limit(200).all()


@app.get("/dashboard/trades", response_model=list[TradeOut])
def get_trades(db: Session = Depends(get_db)) -> list[Trade]:
    return db.query(Trade).order_by(desc(Trade.opened_at)).limit(200).all()


@app.get("/dashboard/signals/live", response_model=list[SignalOut])
def get_live_signals(db: Session = Depends(get_db)) -> list[Signal]:
    return db.query(Signal).order_by(desc(Signal.created_at)).limit(100).all()
