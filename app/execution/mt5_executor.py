"""MetaTrader5 Forex execution adapter."""
import pandas as pd
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.models import TradeSignal

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    mt5 = None

from config import settings


# MT5 timeframe mapping
MT5_TIMEFRAMES = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 16385,
    "H4": 16388,
    "D1": 16408,
}


class MT5Executor:
    """MetaTrader5 execution for Forex."""

    def __init__(self, login: int | None = None, password: str | None = None, server: str | None = None, path: str | None = None):
        self.login = login or settings.MT5_LOGIN
        self.password = password or settings.MT5_PASSWORD
        self.server = server or settings.MT5_SERVER
        self.path = path or settings.MT5_PATH
        self._connected = False

    def connect(self) -> bool:
        if not MT5_AVAILABLE:
            return False
        init_params = {}
        if self.path:
            init_params["path"] = self.path
        if self.login:
            init_params["login"] = self.login
        if self.password:
            init_params["password"] = self.password
        if self.server:
            init_params["server"] = self.server
        self._connected = mt5.initialize(**init_params) if init_params else mt5.initialize()
        return self._connected

    def disconnect(self) -> None:
        if MT5_AVAILABLE and self._connected:
            mt5.shutdown()
            self._connected = False

    def _symbol_info(self, symbol: str):
        if not MT5_AVAILABLE:
            return None
        info = mt5.symbol_info(symbol)
        if info is None:
            symbol = symbol.replace("/", "")
            info = mt5.symbol_info(symbol)
        return info

    def get_ohlcv(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame | None:
        if not MT5_AVAILABLE or not self._connected:
            return None
        tf = MT5_TIMEFRAMES.get(timeframe.upper(), 5)
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if rates is None or len(rates) == 0:
            return None
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.set_index("time", inplace=True)
        return df[["open", "high", "low", "close", "tick_volume"]]

    def get_balance(self, paper: bool) -> float:
        if paper:
            return settings.ACCOUNT_BALANCE
        if not MT5_AVAILABLE or not self._connected:
            return settings.ACCOUNT_BALANCE
        account = mt5.account_info()
        return float(account.balance) if account else settings.ACCOUNT_BALANCE

    def place_order(self, signal: "TradeSignal", size: float, paper: bool) -> str | None:
        if paper:
            return f"PAPER_MT5_{signal.symbol}_{signal.timestamp.timestamp()}"

        if not MT5_AVAILABLE or not self._connected:
            return None

        symbol_info = self._symbol_info(signal.symbol)
        if symbol_info is None:
            return None

        order_type = mt5.ORDER_TYPE_BUY if signal.direction.value == "long" else mt5.ORDER_TYPE_SELL
        price = mt5.symbol_info_tick(signal.symbol).ask if signal.direction.value == "long" else mt5.symbol_info_tick(signal.symbol).bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": signal.symbol,
            "volume": round(size, 2),
            "type": order_type,
            "price": price,
            "sl": signal.stop_loss,
            "tp": signal.tp3,
            "deviation": 20,
            "magic": 234000,
            "comment": f"{signal.strategy.value}",
        }

        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            return str(result.order)
        return None

    def close_position(self, order_id: str, paper: bool) -> bool:
        if paper:
            return True
        if not MT5_AVAILABLE or not self._connected:
            return False
        positions = mt5.positions_get(ticket=int(order_id))
        if not positions:
            return False
        pos = positions[0]
        order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(pos.symbol).bid if pos.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(pos.symbol).ask
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": order_type,
            "position": pos.ticket,
            "price": price,
            "deviation": 20,
        }
        result = mt5.order_send(request)
        return result is not None and result.retcode == mt5.TRADE_RETCODE_DONE
