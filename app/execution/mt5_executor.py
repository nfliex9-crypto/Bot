from datetime import datetime
from uuid import uuid4

from app.execution.base import BrokerExecutor, ExecutionResult, MarketType, OrderRequest

try:
    import MetaTrader5 as mt5  # type: ignore
except Exception:  # pragma: no cover
    mt5 = None


class MT5Executor(BrokerExecutor):
    def __init__(
        self,
        login: int,
        password: str,
        server: str,
        path: str | None = None,
    ) -> None:
        self.login = login
        self.password = password
        self.server = server
        self.path = path
        self._initialized = False

    def _init_terminal(self) -> None:
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package is unavailable in this environment.")
        if self._initialized:
            return
        if not mt5.initialize(path=self.path):
            raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
        if not mt5.login(self.login, password=self.password, server=self.server):
            raise RuntimeError(f"MT5 login failed: {mt5.last_error()}")
        self._initialized = True

    async def submit_order(self, order: OrderRequest) -> ExecutionResult:
        if order.market != "forex":
            raise ValueError("MT5 executor only supports forex orders.")
        self._init_terminal()

        mt5_order_type = mt5.ORDER_TYPE_BUY if order.side == "buy" else mt5.ORDER_TYPE_SELL
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": order.symbol,
            "volume": order.quantity,
            "type": mt5_order_type,
            "price": order.entry_price,
            "sl": order.stop_loss,
            "tp": order.take_profits[-1],
            "deviation": 20,
            "magic": 23032026,
            "comment": "AI_BOT",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is None:
            raise RuntimeError(f"MT5 order_send failed: {mt5.last_error()}")

        return ExecutionResult(
            broker_order_id=str(getattr(result, "order", uuid4())),
            submitted_at=datetime.utcnow(),
            status=str(getattr(result, "retcode", "UNKNOWN")),
            raw={"request": request, "result": str(result)},
        )

    async def close_position(self, symbol: str, market: MarketType) -> None:
        if market != "forex":
            raise ValueError("MT5 executor only supports forex positions.")
        self._init_terminal()
        return None
