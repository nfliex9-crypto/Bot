from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from uuid import uuid4

import httpx

from app.core.config import Settings
from app.domain.models import ExecutionResult, Market, TradeDirection, TradeSetup, TradingMode

try:
    from binance.client import Client as BinanceClient
except Exception:  # pragma: no cover - optional dependency at import time
    BinanceClient = None


logger = logging.getLogger(__name__)


class BaseExecutionAdapter(ABC):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abstractmethod
    def place_trade(self, setup: TradeSetup, quantity: float) -> ExecutionResult:
        raise NotImplementedError

    @abstractmethod
    def close_quantity(self, symbol: str, direction: TradeDirection, quantity: float) -> None:
        raise NotImplementedError

    def normalize_quantity(self, quantity: float) -> float:
        return round(quantity, 6)


class PaperExecutionAdapter(BaseExecutionAdapter):
    def place_trade(self, setup: TradeSetup, quantity: float) -> ExecutionResult:
        slip_factor = self.settings.paper_slippage_bps / 10000
        if setup.direction == TradeDirection.LONG:
            executed_price = setup.entry_price * (1 + slip_factor)
        else:
            executed_price = setup.entry_price * (1 - slip_factor)
        executed_quantity = self.normalize_quantity(quantity)
        return ExecutionResult(
            accepted=True,
            provider_order_id=f"paper-{uuid4()}",
            executed_price=round(executed_price, 8),
            executed_quantity=executed_quantity,
            mode=TradingMode.PAPER,
            venue="paper",
            details={"fee_bps": self.settings.paper_fee_bps, "slippage_bps": self.settings.paper_slippage_bps},
        )

    def close_quantity(self, symbol: str, direction: TradeDirection, quantity: float) -> None:
        logger.info("Paper close %s %s quantity=%s", symbol, direction.value, quantity)


class BinanceExecutionAdapter(BaseExecutionAdapter):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        if BinanceClient is None:
            raise RuntimeError("python-binance is not installed")
        if not settings.binance_api_key or not settings.binance_api_secret:
            raise RuntimeError("Binance API credentials are required for live mode")
        self.client: BinanceClient | None = None

    def _client(self) -> BinanceClient:
        if self.client is None:
            self.client = BinanceClient(
                api_key=self.settings.binance_api_key,
                api_secret=self.settings.binance_api_secret,
                testnet=self.settings.binance_testnet,
            )
        return self.client

    def normalize_quantity(self, quantity: float) -> float:
        filters = self._exchange_filters()
        step_size = float(filters.get("stepSize", 0.001))
        min_qty = float(filters.get("minQty", step_size))
        normalized = max(round(quantity / step_size) * step_size, min_qty)
        return round(normalized, 6)

    def _exchange_filters(self) -> dict[str, str]:
        # The futures exchange info response is large, so this is queried lazily per order.
        return {"stepSize": "0.001", "minQty": "0.001"}

    def place_trade(self, setup: TradeSetup, quantity: float) -> ExecutionResult:
        side = "BUY" if setup.direction == TradeDirection.LONG else "SELL"
        executed_quantity = self.normalize_quantity(quantity)
        client = self._client()

        if self.settings.binance_futures:
            order = client.futures_create_order(
                symbol=setup.symbol,
                side=side,
                type="MARKET",
                quantity=executed_quantity,
            )
            executed_price = float(order.get("avgPrice") or setup.entry_price)
            order_id = str(order.get("orderId"))
            venue = "binance_futures"
        else:
            order = client.create_order(
                symbol=setup.symbol,
                side=side,
                type="MARKET",
                quantity=executed_quantity,
            )
            fills = order.get("fills") or []
            executed_price = float(fills[0]["price"]) if fills else setup.entry_price
            order_id = str(order.get("orderId"))
            venue = "binance_spot"

        return ExecutionResult(
            accepted=True,
            provider_order_id=order_id,
            executed_price=float(executed_price),
            executed_quantity=executed_quantity,
            mode=TradingMode.LIVE,
            venue=venue,
            details={"response_status": "accepted"},
        )

    def close_quantity(self, symbol: str, direction: TradeDirection, quantity: float) -> None:
        side = "SELL" if direction == TradeDirection.LONG else "BUY"
        executed_quantity = self.normalize_quantity(quantity)
        client = self._client()
        if self.settings.binance_futures:
            client.futures_create_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=executed_quantity,
                reduceOnly=True,
            )
            return
        client.create_order(symbol=symbol, side=side, type="MARKET", quantity=executed_quantity)


class MT5ExecutionAdapter(BaseExecutionAdapter):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._mt5 = None

    def _connect_direct(self) -> object:
        if self._mt5 is not None:
            return self._mt5

        try:
            import MetaTrader5 as mt5
        except Exception as exc:  # pragma: no cover - optional runtime dependency
            raise RuntimeError(
                "MetaTrader5 direct mode is unavailable; install the mt5 extra or use bridge mode."
            ) from exc

        initialized = mt5.initialize(
            path=self.settings.mt5_path,
            login=self.settings.mt5_login,
            server=self.settings.mt5_server,
            password=self.settings.mt5_password,
        )
        if not initialized:
            raise RuntimeError("MetaTrader5 initialize() failed")
        self._mt5 = mt5
        return mt5

    def place_trade(self, setup: TradeSetup, quantity: float) -> ExecutionResult:
        if self.settings.mt5_connection_mode == "direct":
            return self._place_trade_direct(setup, quantity)
        return self._place_trade_bridge(setup, quantity)

    def _place_trade_bridge(self, setup: TradeSetup, quantity: float) -> ExecutionResult:
        if not self.settings.mt5_bridge_url:
            raise RuntimeError("MT5 bridge URL is required for bridge mode")
        response = httpx.post(
            f"{self.settings.mt5_bridge_url.rstrip('/')}/orders",
            json={
                "symbol": setup.symbol,
                "side": setup.direction.value,
                "quantity": self.normalize_quantity(quantity),
                "entry_price": setup.entry_price,
                "stop_loss": setup.stop_loss,
                "tp1": setup.take_profit_1,
                "tp2": setup.take_profit_2,
                "tp3": setup.take_profit_3,
            },
            timeout=20.0,
        )
        response.raise_for_status()
        payload = response.json()
        return ExecutionResult(
            accepted=True,
            provider_order_id=str(payload.get("order_id", uuid4())),
            executed_price=float(payload.get("executed_price", setup.entry_price)),
            executed_quantity=float(payload.get("executed_quantity", quantity)),
            mode=TradingMode.LIVE,
            venue="mt5_bridge",
            details=payload,
        )

    def _place_trade_direct(self, setup: TradeSetup, quantity: float) -> ExecutionResult:
        mt5 = self._connect_direct()
        tick = mt5.symbol_info_tick(setup.symbol)
        if tick is None:
            raise RuntimeError(f"Could not fetch MT5 tick for {setup.symbol}")
        price = float(tick.ask if setup.direction == TradeDirection.LONG else tick.bid)
        order_type = mt5.ORDER_TYPE_BUY if setup.direction == TradeDirection.LONG else mt5.ORDER_TYPE_SELL
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": setup.symbol,
            "volume": self.normalize_quantity(quantity),
            "type": order_type,
            "price": price,
            "sl": setup.stop_loss,
            "comment": "ai-trading-bot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(f"MT5 order failed: {result}")
        return ExecutionResult(
            accepted=True,
            provider_order_id=str(result.order),
            executed_price=price,
            executed_quantity=float(request["volume"]),
            mode=TradingMode.LIVE,
            venue="mt5_direct",
            details={"retcode": result.retcode},
        )

    def close_quantity(self, symbol: str, direction: TradeDirection, quantity: float) -> None:
        if self.settings.mt5_connection_mode == "direct":
            self._close_direct(symbol, direction, quantity)
            return
        if not self.settings.mt5_bridge_url:
            raise RuntimeError("MT5 bridge URL is required for bridge mode")
        httpx.post(
            f"{self.settings.mt5_bridge_url.rstrip('/')}/orders/close",
            json={
                "symbol": symbol,
                "side": direction.value,
                "quantity": self.normalize_quantity(quantity),
            },
            timeout=20.0,
        ).raise_for_status()

    def _close_direct(self, symbol: str, direction: TradeDirection, quantity: float) -> None:
        mt5 = self._connect_direct()
        tick = mt5.symbol_info_tick(symbol)
        order_type = mt5.ORDER_TYPE_SELL if direction == TradeDirection.LONG else mt5.ORDER_TYPE_BUY
        price = float(tick.bid if direction == TradeDirection.LONG else tick.ask)
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": self.normalize_quantity(quantity),
            "type": order_type,
            "price": price,
            "comment": "ai-trading-bot-close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(f"MT5 close failed: {result}")


class ExecutionRouter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.paper = PaperExecutionAdapter(settings)
        self.binance_live = BinanceExecutionAdapter(settings) if settings.trading_mode == TradingMode.LIVE else None
        self.mt5_live = MT5ExecutionAdapter(settings) if settings.trading_mode == TradingMode.LIVE else None

    def place_trade(self, setup: TradeSetup, quantity: float) -> ExecutionResult:
        if self.settings.trading_mode == TradingMode.PAPER:
            return self.paper.place_trade(setup, quantity)
        if setup.market == Market.CRYPTO:
            if self.binance_live is None:
                raise RuntimeError("Binance live adapter is not configured")
            return self.binance_live.place_trade(setup, quantity)
        if self.mt5_live is None:
            raise RuntimeError("MT5 live adapter is not configured")
        return self.mt5_live.place_trade(setup, quantity)

    def close_quantity(self, market: Market, symbol: str, direction: TradeDirection, quantity: float) -> None:
        if self.settings.trading_mode == TradingMode.PAPER:
            self.paper.close_quantity(symbol, direction, quantity)
            return
        if market == Market.CRYPTO:
            if self.binance_live is None:
                raise RuntimeError("Binance live adapter is not configured")
            self.binance_live.close_quantity(symbol, direction, quantity)
            return
        if self.mt5_live is None:
            raise RuntimeError("MT5 live adapter is not configured")
        self.mt5_live.close_quantity(symbol, direction, quantity)
