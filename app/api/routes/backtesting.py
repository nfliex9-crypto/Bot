"""
Backtesting API Routes.

POST /backtesting/run       – run backtest for a symbol
GET  /backtesting/results   – list cached backtest results
POST /backtesting/multi     – run across multiple symbols
"""
import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime

from app.backtesting.engine import BacktestEngine, BacktestConfig, BacktestResult
from app.utils.logging_config import get_structured_logger

logger = get_structured_logger("backtesting_api")
router = APIRouter(prefix="/backtesting", tags=["Backtesting"])

# In-memory cache (production would use DB/Redis)
_results_cache: Dict[str, dict] = {}


class BacktestRequest(BaseModel):
    symbol: str = "EURUSD"
    market_type: str = "forex"
    initial_balance: float = Field(3000.0, gt=0)
    risk_per_trade: float = Field(0.0075, gt=0, lt=0.1)
    min_ai_confidence: float = Field(0.60, ge=0.4, le=1.0)
    n_candles_m5: int = Field(2000, ge=200, le=20000)
    spread_multiplier: float = Field(1.0, ge=0.5, le=5.0)
    slippage_factor: float = Field(0.3, ge=0.0, le=2.0)
    use_session_filter: bool = True
    random_seed: int = 42


class MultiBacktestRequest(BaseModel):
    symbols: List[str] = ["EURUSD", "GBPUSD", "BTCUSDT"]
    initial_balance: float = 3000.0
    n_candles_m5: int = 1000
    min_ai_confidence: float = 0.60


def _generate_ohlcv(n: int, freq_min: int, symbol: str, seed: int):
    import pandas as pd
    import numpy as np
    rng = np.random.default_rng(seed)
    dates = pd.date_range(
        end=pd.Timestamp.now(tz="UTC"),
        periods=n,
        freq=f"{freq_min}min",
    )
    base = 1.1 if ("USD" in symbol and "BTC" not in symbol) else 50000.0
    vol = 0.0003 if base < 10 else 50.0
    changes = rng.normal(0, vol, n).cumsum()
    closes = base + changes
    return pd.DataFrame({
        "time": dates,
        "open": closes - rng.uniform(0, vol * 0.5, n),
        "high": closes + rng.uniform(vol * 0.2, vol * 2, n),
        "low": closes - rng.uniform(vol * 0.2, vol * 2, n),
        "close": closes,
        "volume": rng.integers(100, 10000, n).astype(float),
    })


def _run_backtest_sync(req: BacktestRequest) -> dict:
    """Run a single backtest synchronously (called from thread pool)."""
    seed = req.random_seed
    sym_seed = sum(ord(c) for c in req.symbol) + seed

    n_m5 = req.n_candles_m5
    n_m15 = max(n_m5 // 3, 100)
    n_h1 = max(n_m5 // 12, 50)

    m5_df = _generate_ohlcv(n_m5, 5, req.symbol, sym_seed)
    m15_df = _generate_ohlcv(n_m15, 15, req.symbol, sym_seed + 1)
    h1_df = _generate_ohlcv(n_h1, 60, req.symbol, sym_seed + 2)

    config = BacktestConfig(
        symbol=req.symbol,
        market_type=req.market_type,
        initial_balance=req.initial_balance,
        risk_per_trade=req.risk_per_trade,
        min_ai_confidence=req.min_ai_confidence,
        spread_multiplier=req.spread_multiplier,
        slippage_factor=req.slippage_factor,
        use_session_filter=req.use_session_filter,
        random_seed=req.random_seed,
    )

    engine = BacktestEngine(config)
    result = engine.run(h1_df, m15_df, m5_df)

    return {
        "symbol": req.symbol,
        "config": {
            "initial_balance": req.initial_balance,
            "risk_per_trade": req.risk_per_trade,
            "min_ai_confidence": req.min_ai_confidence,
            "n_m5_bars": n_m5,
        },
        "metrics": result.metrics,
        "equity_curve": result.equity_curve[-100:],  # last 100 points
        "trade_count": len(result.trade_log),
        "sample_trades": result.trade_log[:5],
        "duration_seconds": result.duration_seconds,
        "open_at_end": result.open_at_end,
        "error": result.error,
        "run_at": datetime.utcnow().isoformat(),
    }


@router.post("/run")
async def run_backtest(req: BacktestRequest):
    """
    Run a backtest for a single symbol.
    Uses synthetic price data (attach real OHLCV via data provider integration).
    """
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _run_backtest_sync, req)
        _results_cache[req.symbol] = result
        return result
    except Exception as e:
        logger.error(f"Backtest error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/multi")
async def run_multi_backtest(req: MultiBacktestRequest):
    """Run backtests for multiple symbols concurrently."""
    tasks = []
    for sym in req.symbols:
        br = BacktestRequest(
            symbol=sym,
            initial_balance=req.initial_balance,
            n_candles_m5=req.n_candles_m5,
            min_ai_confidence=req.min_ai_confidence,
        )
        loop = asyncio.get_event_loop()
        tasks.append(loop.run_in_executor(None, _run_backtest_sync, br))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    output = []
    for sym, res in zip(req.symbols, results):
        if isinstance(res, Exception):
            output.append({"symbol": sym, "error": str(res)})
        else:
            _results_cache[sym] = res
            output.append(res)

    return {
        "symbols": req.symbols,
        "results": output,
        "run_at": datetime.utcnow().isoformat(),
    }


@router.get("/results")
async def list_results():
    """List all cached backtest results."""
    return {
        "cached_symbols": list(_results_cache.keys()),
        "results": {k: v.get("metrics") for k, v in _results_cache.items()},
    }


@router.get("/results/{symbol}")
async def get_result(symbol: str):
    """Get full cached result for a symbol."""
    if symbol.upper() not in _results_cache:
        raise HTTPException(status_code=404, detail=f"No cached result for {symbol}")
    return _results_cache[symbol.upper()]
