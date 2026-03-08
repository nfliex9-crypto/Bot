"""
MetaTrader 5 Execution Engine

Handles all order management for Forex via MT5:
- Market orders
- Pending orders (limit/stop)
- Order modification (SL/TP update)
- Position management
- Real-time price fetching
- OHLCV data retrieval

Note: MT5 Python API is only available on Windows. On Linux/Mac this module
runs in simulation mode and returns mock responses. For production deployment,
run the MT5 bridge service on a Windows VPS.
"""

import logging
import asyncio
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timezone
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Try to import MetaTrader5 - only available on Windows
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    logger.warning("MetaTrader5 package not available - running in simulation mode")


@dataclass
class OrderResult:
    success: bool
    order_id: Optional[str]
    symbol: str
    direction: str
    lot_size: float
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    error: Optional[str] = None
    raw_response: Optional[dict] = None


@dataclass
class PositionInfo:
    ticket: int
    symbol: str
    direction: str
    lot_size: float
    open_price: float
    current_price: float
    stop_loss: float
    take_profit: float
    pnl: float
    pnl_pct: float


class MT5Executor:
    def __init__(
        self,
        login: int = 0,
        password: str = "",
        server: str = "",
        path: str = "",
        simulation_mode: bool = False,
    ):
        self.login = login
        self.password = password
        self.server = server
        self.path = path
        self.simulation_mode = simulation_mode or not MT5_AVAILABLE
        self.connected = False
        self._sim_tickets = {}
        self._sim_ticket_counter = 10000

    async def connect(self) -> bool:
        if self.simulation_mode:
            self.connected = True
            logger.info("MT5 running in simulation mode")
            return True

        try:
            if not mt5.initialize(
                path=self.path if self.path else None,
                login=self.login,
                password=self.password,
                server=self.server,
            ):
                error = mt5.last_error()
                logger.error(f"MT5 initialization failed: {error}")
                return False

            info = mt5.account_info()
            if info is None:
                logger.error("Failed to get MT5 account info")
                return False

            self.connected = True
            logger.info(f"MT5 connected: {info.name} | Balance: {info.balance} {info.currency}")
            return True
        except Exception as e:
            logger.error(f"MT5 connect error: {e}")
            return False

    async def disconnect(self):
        if not self.simulation_mode and MT5_AVAILABLE and self.connected:
            mt5.shutdown()
        self.connected = False

    async def get_account_info(self) -> Dict:
        if self.simulation_mode:
            return {
                "balance": 10000.0,
                "equity": 10000.0,
                "margin": 0.0,
                "free_margin": 10000.0,
                "currency": "USD",
                "leverage": 100,
                "broker": "Simulation",
            }

        if not self.connected:
            await self.connect()

        info = mt5.account_info()
        if info is None:
            return {}

        return {
            "balance": info.balance,
            "equity": info.equity,
            "margin": info.margin,
            "free_margin": info.margin_free,
            "currency": info.currency,
            "leverage": info.leverage,
            "broker": info.company,
        }

    async def get_current_price(self, symbol: str) -> Optional[Dict]:
        if self.simulation_mode:
            # Generate synthetic price based on symbol
            base_prices = {
                "EURUSD": 1.08500, "GBPUSD": 1.27000, "USDJPY": 149.00,
                "AUDUSD": 0.65000, "USDCAD": 1.36000, "XAUUSD": 2050.00,
            }
            base = base_prices.get(symbol.upper(), 1.0)
            spread_pct = 0.0001
            bid = base * (1 + np.random.normal(0, spread_pct))
            ask = bid + base * 0.0001
            return {"bid": round(bid, 5), "ask": round(ask, 5), "spread": round(ask - bid, 5)}

        if not self.connected:
            return None

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None

        return {"bid": tick.bid, "ask": tick.ask, "spread": tick.ask - tick.bid}

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "H1",
        count: int = 200,
    ) -> Optional[pd.DataFrame]:
        """Fetch OHLCV bars from MT5."""
        if self.simulation_mode:
            return self._generate_sim_ohlcv(symbol, count)

        if not self.connected:
            await self.connect()

        tf_map = {
            "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
        }
        tf = tf_map.get(timeframe.upper(), mt5.TIMEFRAME_H1)
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)

        if rates is None or len(rates) == 0:
            logger.error(f"Failed to fetch rates for {symbol}")
            return None

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df.rename(columns={
            "time": "timestamp", "tick_volume": "volume"
        })[["timestamp", "open", "high", "low", "close", "volume"]]

        return df

    def _generate_sim_ohlcv(self, symbol: str, count: int = 200) -> pd.DataFrame:
        """Generate realistic-looking OHLCV data for simulation."""
        np.random.seed(hash(symbol) % 2**32)
        base_prices = {
            "EURUSD": 1.08500, "GBPUSD": 1.27000, "USDJPY": 149.00,
            "AUDUSD": 0.65000, "XAUUSD": 2050.00,
        }
        base = base_prices.get(symbol.upper().replace("/", ""), 1.0)
        volatility = base * 0.001

        closes = [base]
        for _ in range(count - 1):
            change = np.random.normal(0, volatility)
            closes.append(max(closes[-1] + change, base * 0.5))

        data = []
        for i, close in enumerate(closes):
            open_ = closes[i - 1] if i > 0 else close * 0.9999
            high = max(open_, close) + abs(np.random.normal(0, volatility * 0.5))
            low = min(open_, close) - abs(np.random.normal(0, volatility * 0.5))
            vol = int(np.random.uniform(500, 5000))
            data.append({"open": open_, "high": high, "low": low, "close": close, "volume": vol})

        df = pd.DataFrame(data)
        df.index = pd.date_range(end=datetime.now(timezone.utc), periods=count, freq="1h")
        df.index.name = "timestamp"
        return df.reset_index()

    async def place_market_order(
        self,
        symbol: str,
        direction: str,
        lot_size: float,
        stop_loss: float,
        tp1: float,
        tp2: float,
        tp3: float,
        comment: str = "AI_TRADE",
    ) -> OrderResult:
        """
        Place a market order. Uses TP1 as the primary take profit for the broker.
        TP2 and TP3 are managed manually via the trade manager.
        """
        price_info = await self.get_current_price(symbol)
        if price_info is None:
            return OrderResult(
                success=False, order_id=None, symbol=symbol, direction=direction,
                lot_size=lot_size, entry_price=0.0, stop_loss=stop_loss,
                tp1=tp1, tp2=tp2, tp3=tp3, error="Could not get current price"
            )

        entry_price = price_info["ask"] if direction == "LONG" else price_info["bid"]

        if self.simulation_mode:
            self._sim_ticket_counter += 1
            ticket = str(self._sim_ticket_counter)
            self._sim_tickets[ticket] = {
                "symbol": symbol, "direction": direction, "lot_size": lot_size,
                "entry_price": entry_price, "stop_loss": stop_loss,
                "tp1": tp1, "tp2": tp2, "tp3": tp3, "status": "OPEN",
            }
            logger.info(f"[SIM] MT5 order placed: {symbol} {direction} {lot_size} lots @ {entry_price}")
            return OrderResult(
                success=True, order_id=ticket, symbol=symbol, direction=direction,
                lot_size=lot_size, entry_price=entry_price,
                stop_loss=stop_loss, tp1=tp1, tp2=tp2, tp3=tp3,
            )

        order_type = mt5.ORDER_TYPE_BUY if direction == "LONG" else mt5.ORDER_TYPE_SELL

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot_size,
            "type": order_type,
            "price": entry_price,
            "sl": stop_loss,
            "tp": tp1,
            "deviation": 20,
            "magic": 20240101,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            error = result.comment if result else "Unknown error"
            return OrderResult(
                success=False, order_id=None, symbol=symbol, direction=direction,
                lot_size=lot_size, entry_price=entry_price,
                stop_loss=stop_loss, tp1=tp1, tp2=tp2, tp3=tp3, error=error,
            )

        return OrderResult(
            success=True, order_id=str(result.order), symbol=symbol, direction=direction,
            lot_size=lot_size, entry_price=entry_price,
            stop_loss=stop_loss, tp1=tp1, tp2=tp2, tp3=tp3,
            raw_response={"retcode": result.retcode, "deal": result.deal},
        )

    async def modify_position(
        self,
        ticket: str,
        new_stop_loss: float,
        new_take_profit: Optional[float] = None,
    ) -> bool:
        """Modify an open position's SL/TP."""
        if self.simulation_mode:
            if ticket in self._sim_tickets:
                self._sim_tickets[ticket]["stop_loss"] = new_stop_loss
                if new_take_profit:
                    self._sim_tickets[ticket]["tp1"] = new_take_profit
                logger.info(f"[SIM] Modified position {ticket}: SL={new_stop_loss}")
                return True
            return False

        position = mt5.positions_get(ticket=int(ticket))
        if not position:
            return False

        pos = position[0]
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": int(ticket),
            "sl": new_stop_loss,
            "tp": new_take_profit if new_take_profit else pos.tp,
        }
        result = mt5.order_send(request)
        return result is not None and result.retcode == mt5.TRADE_RETCODE_DONE

    async def close_position(self, ticket: str, symbol: str, lot_size: float, direction: str) -> bool:
        """Close an open position."""
        if self.simulation_mode:
            if ticket in self._sim_tickets:
                self._sim_tickets[ticket]["status"] = "CLOSED"
                logger.info(f"[SIM] Closed position {ticket}")
                return True
            return False

        price_info = await self.get_current_price(symbol)
        if not price_info:
            return False

        close_type = mt5.ORDER_TYPE_SELL if direction == "LONG" else mt5.ORDER_TYPE_BUY
        close_price = price_info["bid"] if direction == "LONG" else price_info["ask"]

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": int(ticket),
            "symbol": symbol,
            "volume": lot_size,
            "type": close_type,
            "price": close_price,
            "deviation": 20,
            "magic": 20240101,
            "comment": "AI_CLOSE",
        }
        result = mt5.order_send(request)
        return result is not None and result.retcode == mt5.TRADE_RETCODE_DONE
