from datetime import datetime
from uuid import uuid4

from app.execution.base import BrokerExecutor, ExecutionResult, MarketType, OrderRequest


class PaperExecutor(BrokerExecutor):
    async def submit_order(self, order: OrderRequest) -> ExecutionResult:
        return ExecutionResult(
            broker_order_id=f"paper-{uuid4()}",
            submitted_at=datetime.utcnow(),
            status="filled",
            raw={"order": order.__dict__, "simulated": True},
        )

    async def close_position(self, symbol: str, market: MarketType) -> None:
        return None
