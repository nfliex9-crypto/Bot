from datetime import datetime
from uuid import uuid4

from binance import AsyncClient

from app.execution.base import BrokerExecutor, ExecutionResult, MarketType, OrderRequest


class BinanceExecutor(BrokerExecutor):
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self._client: AsyncClient | None = None

    async def _client_or_create(self) -> AsyncClient:
        if self._client is None:
            self._client = await AsyncClient.create(
                api_key=self.api_key,
                api_secret=self.api_secret,
                testnet=self.testnet,
            )
        return self._client

    async def submit_order(self, order: OrderRequest) -> ExecutionResult:
        if order.market != "crypto":
            raise ValueError("Binance executor only supports crypto orders.")

        client = await self._client_or_create()
        response = await client.create_order(
            symbol=order.symbol,
            side="BUY" if order.side == "buy" else "SELL",
            type="MARKET",
            quantity=order.quantity,
            newClientOrderId=f"bot-{uuid4().hex[:24]}",
        )
        return ExecutionResult(
            broker_order_id=response.get("orderId", ""),
            submitted_at=datetime.utcnow(),
            status=response.get("status", "NEW"),
            raw=response,
        )

    async def close_position(self, symbol: str, market: MarketType) -> None:
        if market != "crypto":
            raise ValueError("Binance executor only supports crypto positions.")
        # Production close logic should inspect open position quantity.
        return None
