import asyncio
import json
from datetime import datetime, timezone
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.trading_service import get_execution_engine
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["WebSocket"])


class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info("WebSocket client connected", total=len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info("WebSocket client disconnected", total=len(self.active_connections))

    async def broadcast(self, message: dict):
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)
        self.active_connections -= disconnected


manager = ConnectionManager()


@router.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    """Real-time dashboard data stream."""
    await manager.connect(websocket)
    engine = get_execution_engine()

    try:
        while True:
            try:
                dashboard = await engine.get_dashboard_data()
                dashboard["timestamp"] = datetime.now(timezone.utc).isoformat()
                dashboard["type"] = "dashboard_update"
                await websocket.send_json(dashboard)
            except Exception as e:
                logger.error("Dashboard data error", error=str(e))

            await asyncio.sleep(5)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.websocket("/ws/signals")
async def signals_websocket(websocket: WebSocket):
    """Real-time trade signal stream."""
    await manager.connect(websocket)
    engine = get_execution_engine()

    try:
        while True:
            try:
                signals = await engine.scan_markets()
                if signals:
                    await websocket.send_json({
                        "type": "signals_update",
                        "signals": signals[:10],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
            except Exception as e:
                logger.error("Signal stream error", error=str(e))

            await asyncio.sleep(60)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.websocket("/ws/trades")
async def trades_websocket(websocket: WebSocket):
    """Real-time trade monitoring stream."""
    await manager.connect(websocket)
    engine = get_execution_engine()

    try:
        while True:
            try:
                actions = await engine.monitor_positions()
                if actions:
                    await websocket.send_json({
                        "type": "trade_actions",
                        "actions": actions,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                active = [
                    {
                        "order_id": t.order_id,
                        "symbol": t.symbol,
                        "direction": t.direction,
                        "entry": t.entry_price,
                        "sl": t.stop_loss,
                        "tp1_hit": t.tp1_hit,
                        "tp2_hit": t.tp2_hit,
                    }
                    for t in engine.risk_manager.active_trades.values()
                ]
                await websocket.send_json({
                    "type": "active_trades",
                    "trades": active,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as e:
                logger.error("Trade stream error", error=str(e))

            await asyncio.sleep(10)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
