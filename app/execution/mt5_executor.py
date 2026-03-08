from __future__ import annotations

from app.execution.base import BaseExecutor, OrderRequest, OrderResult

try:
    import MetaTrader5 as mt5
except Exception:  # pragma: no cover
    mt5 = None  # type: ignore[assignment]


class MT5Executor(BaseExecutor):
    def __init__(self, login: int, password: str, server: str, path: str | None = None):
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package is unavailable.")

        initialized = mt5.initialize(path=path, login=login, password=password, server=server)
        if not initialized:
            raise RuntimeError(f"Failed to initialize MT5: {mt5.last_error()}")

    def place_order(self, request: OrderRequest) -> OrderResult:
        if mt5 is None:
            return OrderResult(False, None, request.price, "MT5 package unavailable.")
        tick = mt5.symbol_info_tick(request.symbol)
        if tick is None:
            return OrderResult(False, None, request.price, f"No tick for {request.symbol}")

        order_type = mt5.ORDER_TYPE_BUY if request.side == "buy" else mt5.ORDER_TYPE_SELL
        price = tick.ask if request.side == "buy" else tick.bid
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": request.symbol,
            "volume": float(round(request.quantity, 2)),
            "type": order_type,
            "price": price,
            "sl": request.stop_loss,
            "deviation": 20,
            "magic": 20260308,
            "comment": "ai-bot",
            "type_filling": mt5.ORDER_FILLING_FOK,
        }
        result = mt5.order_send(req)
        if result is None:
            return OrderResult(False, None, price, "MT5 order_send returned None")
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return OrderResult(False, None, price, f"MT5 retcode={result.retcode}")
        return OrderResult(True, str(result.order), float(price), "MT5 order executed.")

    def close_partial(self, symbol: str, side: str, quantity: float) -> OrderResult:
        if mt5 is None:
            return OrderResult(False, None, 0.0, "MT5 package unavailable.")
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return OrderResult(False, None, 0.0, f"No tick for {symbol}")
        close_type = mt5.ORDER_TYPE_SELL if side == "buy" else mt5.ORDER_TYPE_BUY
        price = tick.bid if side == "buy" else tick.ask
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(round(quantity, 2)),
            "type": close_type,
            "price": price,
            "deviation": 20,
            "magic": 20260308,
            "comment": "ai-bot-partial-close",
            "type_filling": mt5.ORDER_FILLING_FOK,
        }
        result = mt5.order_send(req)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            return OrderResult(False, None, price, "MT5 partial close failed.")
        return OrderResult(True, str(result.order), price, "MT5 partial close executed.")

