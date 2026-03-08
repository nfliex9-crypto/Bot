"""
WebSocket endpoint for real-time signal and price broadcasting.
"""

import json
import logging
import asyncio
from typing import Set, Dict
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: Dict):
        """Send a message to all connected clients."""
        if not self.active_connections:
            return

        msg_str = json.dumps(message)
        disconnected = set()

        for ws in list(self.active_connections):
            try:
                await ws.send_text(msg_str)
            except Exception:
                disconnected.add(ws)

        if disconnected:
            async with self._lock:
                self.active_connections -= disconnected

    async def send_personal(self, websocket: WebSocket, message: Dict):
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")

    @property
    def connection_count(self) -> int:
        return len(self.active_connections)


manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket handler for live trading data."""
    await manager.connect(websocket)

    # Send initial connection confirmation
    await manager.send_personal(websocket, {
        "type": "connection",
        "status": "connected",
        "message": "Connected to AI Trading System live feed",
    })

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                msg = json.loads(data)

                # Handle ping/pong
                if msg.get("type") == "ping":
                    await manager.send_personal(websocket, {"type": "pong"})
                elif msg.get("type") == "subscribe":
                    await manager.send_personal(websocket, {
                        "type": "subscribed",
                        "channels": msg.get("channels", []),
                    })
            except asyncio.TimeoutError:
                # Send heartbeat
                await manager.send_personal(websocket, {"type": "heartbeat"})

    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await manager.disconnect(websocket)
