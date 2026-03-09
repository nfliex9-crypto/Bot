"""
Strategy Discovery API routes.

Provides endpoints to trigger and monitor the automated strategy
discovery pipeline.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from app.utils.logger import get_logger

logger = get_logger("api.discovery")

router = APIRouter(prefix="/discovery", tags=["Strategy Discovery"])

_running = False
_last_report: Optional[dict] = None


class DiscoveryRequest(BaseModel):
    candles: int = 20_000
    strategies: int = 200
    seed: int = 42
    top_n: int = 5
    balance: float = 10_000.0


def _run_discovery(params: DiscoveryRequest):
    global _running, _last_report
    try:
        from app.discovery.backtest import BacktestConfig
        from app.discovery.engine import DiscoveryEngine

        bt_cfg = BacktestConfig(initial_balance=params.balance)
        engine = DiscoveryEngine(
            n_candles=params.candles,
            n_strategies=params.strategies,
            seed=params.seed,
            bt_cfg=bt_cfg,
            verbose=False,
        )
        report = engine.run(top_n=params.top_n)
        _last_report = {
            "status": "completed",
            "total_generated": report.total_generated,
            "passed_first_filter": report.passed_first_filter,
            "passed_walkforward": report.passed_walkforward,
            "total_ranked": report.total_ranked,
            "elapsed_seconds": report.elapsed_seconds,
            "module_path": report.module_path,
            "export_dir": report.export_dir,
            "top_strategies": [
                {
                    "name": rs.strategy.name,
                    "family": rs.strategy.family,
                    "composite_score": rs.composite_score,
                    "description": rs.strategy.description,
                    "oos_sharpe": rs.oos_report.sharpe_ratio,
                    "oos_profit_factor": rs.oos_report.profit_factor,
                    "oos_max_drawdown": rs.oos_report.max_drawdown,
                    "oos_win_rate": rs.oos_report.win_rate,
                    "oos_trades": rs.oos_report.total_trades,
                }
                for rs in report.top_strategies
            ],
        }
    except Exception as e:
        logger.error(f"Discovery pipeline error: {e}", exc_info=True)
        _last_report = {"status": "error", "error": str(e)}
    finally:
        _running = False


@router.post("/run")
async def run_discovery(
    params: DiscoveryRequest,
    background_tasks: BackgroundTasks,
):
    """
    Trigger the strategy discovery pipeline (runs in background).

    The pipeline generates strategies, backtests them, applies
    walk-forward validation, and exports the top performers.
    """
    global _running
    if _running:
        raise HTTPException(409, "Discovery pipeline already running")

    _running = True
    background_tasks.add_task(_run_discovery, params)
    return {"status": "started", "message": "Discovery pipeline running in background"}


@router.get("/status")
async def discovery_status():
    """Check the status of the last discovery run."""
    if _running:
        return {"status": "running"}
    if _last_report is None:
        return {"status": "idle", "message": "No discovery run yet"}
    return _last_report


@router.get("/strategies")
async def list_discovered_strategies(
    top_n: int = Query(5, ge=1, le=50),
):
    """Return the top strategies from the last discovery run."""
    if _last_report is None or _last_report.get("status") != "completed":
        raise HTTPException(404, "No completed discovery run available")
    strats = _last_report.get("top_strategies", [])
    return {"strategies": strats[:top_n]}
