from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.execution.base import ExecutionResult, OrderRequest


class PaperExecutor:
    def place_order(self, req: OrderRequest) -> ExecutionResult:
        return ExecutionResult(
            accepted=True,
            order_id=f"paper-{uuid4().hex[:12]}",
            message="Paper order accepted",
            raw={
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "symbol": req.symbol,
                "market_type": req.market_type,
                "side": req.side,
                "qty": req.quantity,
                "entry_price": req.entry_price,
                "stop_loss": req.stop_loss,
                "tp1": req.tp1,
                "tp2": req.tp2,
                "tp3": req.tp3,
                "confidence": req.confidence,
                "metadata": req.metadata,
            },
        )

