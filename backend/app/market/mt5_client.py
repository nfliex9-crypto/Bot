from __future__ import annotations

from datetime import datetime

import pandas as pd


class MT5Client:
    def __init__(self, login: str | None, password: str | None, server: str | None, path: str | None):
        self.login = int(login) if login else None
        self.password = password
        self.server = server
        self.path = path
        self.mt5 = None
        self.connected = False

        try:
            import MetaTrader5 as mt5

            self.mt5 = mt5
        except Exception:
            self.mt5 = None

    def connect(self) -> bool:
        if self.mt5 is None:
            self.connected = False
            return False

        if not self.mt5.initialize(path=self.path):
            self.connected = False
            return False

        if self.login and self.password and self.server:
            self.connected = self.mt5.login(self.login, password=self.password, server=self.server)
        else:
            self.connected = True

        return self.connected

    def get_rates(self, symbol: str, timeframe: int = 5, limit: int = 200) -> pd.DataFrame:
        if not self.connected:
            self.connect()

        if self.mt5 is None or not self.connected:
            return pd.DataFrame()

        timeframe_map = {
            1: self.mt5.TIMEFRAME_M1,
            5: self.mt5.TIMEFRAME_M5,
            15: self.mt5.TIMEFRAME_M15,
            60: self.mt5.TIMEFRAME_H1,
        }
        tf = timeframe_map.get(timeframe, self.mt5.TIMEFRAME_M5)

        rates = self.mt5.copy_rates_from_pos(symbol, tf, 0, limit)
        if rates is None or len(rates) == 0:
            return pd.DataFrame()

        frame = pd.DataFrame(rates)
        frame["time"] = pd.to_datetime(frame["time"], unit="s")
        frame = frame.rename(columns={"tick_volume": "volume"})
        return frame[["time", "open", "high", "low", "close", "volume"]]

    def place_market_order(self, symbol: str, side: str, volume: float, sl: float, tp: float) -> dict:
        if not self.connected:
            self.connect()

        if self.mt5 is None or not self.connected:
            return {"ok": False, "simulated": True, "reason": "mt5_unavailable"}

        symbol_info = self.mt5.symbol_info(symbol)
        if symbol_info is None:
            return {"ok": False, "simulated": True, "reason": "unknown_symbol"}

        tick = self.mt5.symbol_info_tick(symbol)
        if tick is None:
            return {"ok": False, "simulated": True, "reason": "no_tick"}

        order_type = self.mt5.ORDER_TYPE_BUY if side == "BUY" else self.mt5.ORDER_TYPE_SELL
        price = tick.ask if side == "BUY" else tick.bid

        request = {
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": max(volume, symbol_info.volume_min),
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 777001,
            "comment": f"ai-trader-{datetime.utcnow().isoformat()}",
            "type_filling": self.mt5.ORDER_FILLING_IOC,
            "type_time": self.mt5.ORDER_TIME_GTC,
        }

        result = self.mt5.order_send(request)
        if result is None:
            return {"ok": False, "simulated": True, "reason": "mt5_order_failed"}

        return {
            "ok": result.retcode == self.mt5.TRADE_RETCODE_DONE,
            "simulated": False,
            "order_id": str(getattr(result, "order", "")),
            "retcode": int(result.retcode),
        }
