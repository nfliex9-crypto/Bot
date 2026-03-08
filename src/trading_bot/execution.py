from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from .domain import MarketType, PositionPlan, TradeDirection
from .models import TradeRecord

try:
    from binance.client import Client as BinanceClient
except Exception:  # pragma: no cover - optional dependency may fail outside live environment
    BinanceClient = None

try:
    import MetaTrader5 as mt5
except Exception:  # pragma: no cover - optional dependency may fail outside live environment
    mt5 = None


@dataclass(slots=True)
class ExecutionResult:
    broker_trade_id: str
    status: str = "open"


class ExecutionAdapter(ABC):
    market: MarketType

    @abstractmethod
    def place_trade(self, plan: PositionPlan) -> ExecutionResult:
        raise NotImplementedError

    @abstractmethod
    def close_partial(self, trade: TradeRecord, quantity: float) -> None:
        raise NotImplementedError

    @abstractmethod
    def modify_stop(self, trade: TradeRecord, new_stop: float) -> None:
        raise NotImplementedError


class PaperExecutionAdapter(ExecutionAdapter):
    def __init__(self, market: MarketType) -> None:
        self.market = market

    def place_trade(self, plan: PositionPlan) -> ExecutionResult:
        return ExecutionResult(broker_trade_id=f"paper-{plan.symbol}-{uuid4().hex[:12]}")

    def close_partial(self, trade: TradeRecord, quantity: float) -> None:
        return None

    def modify_stop(self, trade: TradeRecord, new_stop: float) -> None:
        return None


class BinanceFuturesExecutionAdapter(ExecutionAdapter):
    market = MarketType.CRYPTO

    def __init__(self, api_key: str | None, api_secret: str | None, testnet: bool = True) -> None:
        if BinanceClient is None:
            raise RuntimeError("python-binance is not installed")
        self.client = BinanceClient(api_key=api_key, api_secret=api_secret, testnet=testnet)

    def place_trade(self, plan: PositionPlan) -> ExecutionResult:
        side = "BUY" if plan.direction == TradeDirection.LONG else "SELL"
        response = self.client.futures_create_order(
            symbol=plan.symbol,
            side=side,
            type="MARKET",
            quantity=plan.quantity,
        )
        return ExecutionResult(broker_trade_id=str(response["orderId"]))

    def close_partial(self, trade: TradeRecord, quantity: float) -> None:
        side = "SELL" if trade.direction == TradeDirection.LONG.value else "BUY"
        self.client.futures_create_order(
            symbol=trade.symbol,
            side=side,
            type="MARKET",
            quantity=quantity,
            reduceOnly=True,
        )

    def modify_stop(self, trade: TradeRecord, new_stop: float) -> None:
        # Stops are managed by the application loop for simplicity and portability.
        return None


class MT5ExecutionAdapter(ExecutionAdapter):
    market = MarketType.FOREX

    def __init__(self) -> None:
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package is not installed")

    def place_trade(self, plan: PositionPlan) -> ExecutionResult:
        tick = mt5.symbol_info_tick(plan.symbol)
        side = mt5.ORDER_TYPE_BUY if plan.direction == TradeDirection.LONG else mt5.ORDER_TYPE_SELL
        price = tick.ask if side == mt5.ORDER_TYPE_BUY else tick.bid
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": plan.symbol,
            "volume": plan.quantity,
            "type": side,
            "price": price,
            "sl": plan.stop_loss,
            "deviation": 20,
            "magic": 880001,
            "comment": "ai-bot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(f"MT5 order failed: {getattr(result, 'comment', 'unknown error')}")
        return ExecutionResult(broker_trade_id=str(result.order))

    def close_partial(self, trade: TradeRecord, quantity: float) -> None:
        position_ticket = int(trade.broker_trade_id) if trade.broker_trade_id else 0
        position = mt5.positions_get(ticket=position_ticket)
        if not position:
            return
        ticket = position[0].ticket
        symbol = trade.symbol
        tick = mt5.symbol_info_tick(symbol)
        order_type = mt5.ORDER_TYPE_SELL if trade.direction == TradeDirection.LONG.value else mt5.ORDER_TYPE_BUY
        price = tick.bid if order_type == mt5.ORDER_TYPE_SELL else tick.ask
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": ticket,
            "symbol": symbol,
            "volume": quantity,
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": 880001,
            "comment": "ai-bot-partial",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        mt5.order_send(request)

    def modify_stop(self, trade: TradeRecord, new_stop: float) -> None:
        if not trade.broker_trade_id:
            return
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": int(trade.broker_trade_id),
            "sl": new_stop,
            "tp": 0.0,
        }
        mt5.order_send(request)


def new_trade_timestamp() -> datetime:
    return datetime.now(timezone.utc)
