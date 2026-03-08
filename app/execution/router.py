from app.config import Settings
from app.execution.base import BrokerExecutor, OrderRequest
from app.execution.binance_executor import BinanceExecutor
from app.execution.mt5_executor import MT5Executor
from app.execution.paper import PaperExecutor


class ExecutionRouter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.paper = PaperExecutor()
        self.mt5 = MT5Executor(settings)
        self.binance = BinanceExecutor(settings)

    def _executor(self, market_type: str) -> BrokerExecutor:
        if self.settings.trading_mode == "paper":
            return self.paper
        if market_type == "forex":
            return self.mt5
        if market_type == "crypto":
            return self.binance
        raise ValueError(f"Unsupported market type: {market_type}")

    def execute(self, req: OrderRequest):
        executor = self._executor(req.market_type)
        return executor.place_order(req)

