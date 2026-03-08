from dataclasses import dataclass

from app.market.binance_client import BinanceMarketClient
from app.market.mt5_client import MT5Client


@dataclass
class ExecutionResult:
    executed: bool
    simulated: bool
    order_id: str | None
    reason: str


class ExecutionEngine:
    def __init__(self, mt5_client: MT5Client, binance_client: BinanceMarketClient):
        self.mt5_client = mt5_client
        self.binance_client = binance_client

    def execute(self, market: str, symbol: str, side: str, quantity: float, stop_loss: float, tp1: float) -> ExecutionResult:
        if market == "FOREX":
            result = self.mt5_client.place_market_order(symbol=symbol, side=side, volume=quantity, sl=stop_loss, tp=tp1)
        else:
            result = self.binance_client.place_market_order(symbol=symbol, side=side, quantity=quantity)

        return ExecutionResult(
            executed=bool(result.get("ok", False)),
            simulated=bool(result.get("simulated", False)),
            order_id=result.get("order_id"),
            reason=result.get("reason", "executed" if result.get("ok") else "execution_failed"),
        )
