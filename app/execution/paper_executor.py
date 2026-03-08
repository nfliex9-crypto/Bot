from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.execution.base import BaseExecutor, OrderRequest, OrderResult


class PaperExecutor(BaseExecutor):
    def place_order(self, request: OrderRequest) -> OrderResult:
        ref = f"paper-{request.symbol}-{uuid4().hex[:12]}"
        return OrderResult(
            success=True,
            execution_ref=ref,
            filled_price=request.price,
            message=f"Paper order accepted at {datetime.now(UTC).isoformat()}",
        )

    def close_partial(self, symbol: str, side: str, quantity: float) -> OrderResult:
        ref = f"paper-close-{symbol}-{uuid4().hex[:10]}"
        return OrderResult(
            success=True,
            execution_ref=ref,
            filled_price=0.0,
            message=f"Paper partial close {side} qty={quantity}",
        )

