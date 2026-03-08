from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from app.core.config import get_settings
from app.db.models import MarketType, RecordStatus, Trade

logger = logging.getLogger(__name__)
settings = get_settings()

try:
    import MetaTrader5 as mt5  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    mt5 = None

try:
    from binance.spot import Spot  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    Spot = None


@dataclass
class ExecutionResult:
    status: RecordStatus
    execution_id: str
    broker: str
    details: dict


class ExecutionService:
    def execute_trade(self, trade: Trade) -> ExecutionResult:
        if settings.paper_trading:
            return self._simulate(trade, "paper")

        if trade.market == MarketType.FOREX:
            return self._execute_mt5(trade)
        return self._execute_binance(trade)

    def move_stop_to_break_even(self, trade: Trade) -> ExecutionResult:
        details = {"action": "move_stop_to_break_even", "trade_id": trade.id, "timestamp": datetime.now(UTC).isoformat()}
        if settings.paper_trading:
            return ExecutionResult(
                status=RecordStatus.SIMULATED,
                execution_id=trade.execution_id or f"paper-{uuid4()}",
                broker=trade.broker,
                details=details,
            )

        logger.info("Break-even stop update requested for trade %s", trade.id)
        return ExecutionResult(
            status=trade.status,
            execution_id=trade.execution_id or f"be-{uuid4()}",
            broker=trade.broker,
            details=details,
        )

    def _execute_mt5(self, trade: Trade) -> ExecutionResult:
        if mt5 is None:
            return self._simulate(trade, "mt5-simulated")

        if not mt5.initialize(path=settings.mt5_path):
            logger.warning("MT5 initialize failed, simulating execution.")
            return self._simulate(trade, "mt5-simulated")

        if settings.mt5_login and settings.mt5_password and settings.mt5_server:
            authorized = mt5.login(
                login=int(settings.mt5_login),
                password=settings.mt5_password,
                server=settings.mt5_server,
            )
            if not authorized:
                logger.warning("MT5 login failed, simulating execution.")
                return self._simulate(trade, "mt5-simulated")

        order_type = mt5.ORDER_TYPE_BUY if trade.side.value == "long" else mt5.ORDER_TYPE_SELL
        tick = mt5.symbol_info_tick(trade.symbol)
        price = tick.ask if trade.side.value == "long" else tick.bid
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": trade.symbol,
            "volume": trade.quantity,
            "type": order_type,
            "price": price,
            "sl": trade.stop_loss,
            "tp": trade.tp3,
            "comment": "AI Automated Trading System",
        }
        result = mt5.order_send(request)
        if result is None:
            return self._simulate(trade, "mt5-simulated")

        return ExecutionResult(
            status=RecordStatus.OPEN,
            execution_id=str(getattr(result, "order", uuid4())),
            broker="MetaTrader5",
            details={"retcode": getattr(result, "retcode", None), "request": request},
        )

    def _execute_binance(self, trade: Trade) -> ExecutionResult:
        if Spot is None or not settings.binance_api_key or not settings.binance_api_secret:
            return self._simulate(trade, "binance-simulated")

        client = Spot(api_key=settings.binance_api_key, api_secret=settings.binance_api_secret, base_url=settings.binance_base_url)
        side = "BUY" if trade.side.value == "long" else "SELL"
        try:
            response = client.new_order(
                symbol=trade.symbol,
                side=side,
                type="MARKET",
                quantity=trade.quantity,
            )
        except Exception as exc:  # pragma: no cover - exchange response is external
            logger.warning("Binance order failed, simulating execution: %s", exc)
            return self._simulate(trade, "binance-simulated")

        return ExecutionResult(
            status=RecordStatus.OPEN,
            execution_id=str(response.get("orderId", uuid4())),
            broker="Binance",
            details=response,
        )

    @staticmethod
    def _simulate(trade: Trade, broker: str) -> ExecutionResult:
        return ExecutionResult(
            status=RecordStatus.SIMULATED,
            execution_id=f"sim-{uuid4()}",
            broker=broker,
            details={
                "symbol": trade.symbol,
                "market": trade.market.value,
                "side": trade.side.value,
                "entry_price": trade.entry_price,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
