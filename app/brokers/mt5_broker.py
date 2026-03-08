"""
MetaTrader 5 Broker Connector.

Note: The MetaTrader5 Python library only runs natively on Windows.
On Linux/Docker, either:
  1. Use a Windows host with MT5 installed and connect via network bridge
  2. Run the bot in paper mode for Linux deployments
  3. Use a cloud Windows VM for MT5 execution only

This implementation gracefully handles Linux environments by
falling back to paper mode when MT5 is not available.
"""
import platform
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
import pandas as pd
import pytz

from app.brokers.base import BaseBroker, OrderResult, TickData, OHLCV, AccountInfo
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("mt5_broker")

MT5_AVAILABLE = False
mt5 = None

if platform.system() == "Windows":
    try:
        import MetaTrader5 as mt5
        MT5_AVAILABLE = True
        logger.info("MetaTrader5 library loaded successfully")
    except ImportError:
        logger.warning("MetaTrader5 library not available on this platform")
else:
    logger.info("MT5 broker: running on Linux, paper mode only for MT5")


# Timeframe mapping: string → MT5 timeframe constant
MT5_TIMEFRAMES = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 16385,
    "H4": 16388,
    "D1": 16408,
    "W1": 32769,
    "MN1": 49153,
}


class MT5PaperAccount:
    """Simulated account for paper trading on Linux."""

    def __init__(self, balance: float = 3000.0):
        self.balance = balance
        self.equity = balance
        self.margin = 0.0
        self.free_margin = balance
        self.orders: List[Dict] = []
        self._next_ticket = 1000

    def next_ticket(self) -> str:
        t = str(self._next_ticket)
        self._next_ticket += 1
        return t


class MT5Broker(BaseBroker):
    """
    MetaTrader 5 broker connector.

    In live mode (Windows only): connects to MT5 terminal and executes real trades.
    In paper mode or on Linux: simulates execution using synthetic data.
    """

    def __init__(self, paper_mode: bool = None):
        _paper = paper_mode if paper_mode is not None else settings.is_paper
        super().__init__(paper_mode=_paper or not MT5_AVAILABLE)
        self._paper_account = MT5PaperAccount(settings.ACCOUNT_BALANCE)
        self._utc = pytz.UTC

    async def connect(self) -> bool:
        """Initialize MT5 connection."""
        if self.paper_mode or not MT5_AVAILABLE:
            self._connected = True
            logger.info("MT5 broker: connected in paper/simulation mode")
            return True

        try:
            kwargs = {}
            if settings.MT5_PATH:
                kwargs["path"] = settings.MT5_PATH

            if not mt5.initialize(**kwargs):
                logger.error(f"MT5 initialize failed: {mt5.last_error()}")
                return False

            if settings.MT5_LOGIN and settings.MT5_PASSWORD:
                authorized = mt5.login(
                    login=settings.MT5_LOGIN,
                    password=settings.MT5_PASSWORD,
                    server=settings.MT5_SERVER or "",
                )
                if not authorized:
                    logger.error(f"MT5 login failed: {mt5.last_error()}")
                    return False

            self._connected = True
            info = mt5.account_info()
            logger.info(
                f"MT5 connected: account={info.login} balance={info.balance} "
                f"currency={info.currency}"
            )
            return True

        except Exception as e:
            logger.error(f"MT5 connection error: {e}")
            return False

    async def disconnect(self):
        """Shutdown MT5."""
        if MT5_AVAILABLE and not self.paper_mode and self._connected:
            try:
                mt5.shutdown()
            except Exception:
                pass
        self._connected = False
        logger.info("MT5 broker disconnected")

    async def get_account_info(self) -> AccountInfo:
        if self.paper_mode or not MT5_AVAILABLE:
            acc = self._paper_account
            return AccountInfo(
                balance=acc.balance,
                equity=acc.equity,
                margin=acc.margin,
                free_margin=acc.free_margin,
                margin_level=0.0,
                currency="USD",
                leverage=100,
                profit=0.0,
            )

        try:
            info = mt5.account_info()
            return AccountInfo(
                balance=float(info.balance),
                equity=float(info.equity),
                margin=float(info.margin),
                free_margin=float(info.margin_free),
                margin_level=float(info.margin_level),
                currency=info.currency,
                leverage=int(info.leverage),
                profit=float(info.profit),
            )
        except Exception as e:
            logger.error(f"MT5 get_account_info error: {e}")
            return AccountInfo(balance=0, equity=0, margin=0, free_margin=0, margin_level=0)

    async def get_tick(self, symbol: str) -> Optional[TickData]:
        if self.paper_mode or not MT5_AVAILABLE:
            return await self._get_simulated_tick(symbol)

        try:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return None
            return TickData(
                symbol=symbol,
                bid=float(tick.bid),
                ask=float(tick.ask),
                last=float(tick.last),
                spread=float(tick.ask - tick.bid),
                timestamp=datetime.fromtimestamp(tick.time, tz=self._utc),
            )
        except Exception as e:
            logger.error(f"MT5 get_tick error ({symbol}): {e}")
            return None

    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        count: int = 200,
    ) -> Optional[OHLCV]:
        if self.paper_mode or not MT5_AVAILABLE:
            return await self._get_simulated_ohlcv(symbol, timeframe, count)

        try:
            tf = self._normalize_timeframe(timeframe)
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
            if rates is None or len(rates) == 0:
                logger.warning(f"MT5: no data for {symbol} {timeframe}")
                return None

            df = pd.DataFrame(rates)
            df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
            df = df.rename(columns={
                "tick_volume": "volume",
                "spread": "spread",
                "real_volume": "real_volume",
            })
            df = df[["time", "open", "high", "low", "close", "volume"]].copy()
            df = df.sort_values("time").reset_index(drop=True)

            return OHLCV(symbol=symbol, timeframe=timeframe, data=df)

        except Exception as e:
            logger.error(f"MT5 get_ohlcv error ({symbol} {timeframe}): {e}")
            return None

    async def place_order(
        self,
        symbol: str,
        direction: str,
        lot_size: float,
        stop_loss: float,
        take_profit: float,
        comment: str = "AIBot",
    ) -> OrderResult:
        if self.paper_mode or not MT5_AVAILABLE:
            return await self._place_paper_order(
                symbol, direction, lot_size, stop_loss, take_profit, comment
            )

        try:
            order_type = mt5.ORDER_TYPE_BUY if direction == "long" else mt5.ORDER_TYPE_SELL
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return OrderResult(success=False, error="Cannot get tick data")

            price = tick.ask if direction == "long" else tick.bid

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(lot_size),
                "type": order_type,
                "price": price,
                "sl": float(stop_loss),
                "tp": float(take_profit),
                "deviation": 20,
                "magic": 123456,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(request)

            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"MT5 order failed: {result.retcode} - {result.comment}")
                return OrderResult(
                    success=False,
                    error=f"MT5 error {result.retcode}: {result.comment}",
                )

            logger.info(
                f"TRADE MT5 order placed: {symbol} {direction} {lot_size} lots "
                f"ticket={result.order} @ {result.price}"
            )

            return OrderResult(
                success=True,
                order_id=str(result.order),
                ticket=str(result.order),
                symbol=symbol,
                direction=direction,
                lot_size=lot_size,
                entry_price=result.price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                raw={"retcode": result.retcode, "volume": result.volume},
            )

        except Exception as e:
            logger.error(f"MT5 place_order error: {e}")
            return OrderResult(success=False, error=str(e))

    async def close_order(
        self,
        ticket: str,
        lot_size: Optional[float] = None,
    ) -> OrderResult:
        if self.paper_mode or not MT5_AVAILABLE:
            return await self._close_paper_order(ticket, lot_size)

        try:
            position = None
            positions = mt5.positions_get(ticket=int(ticket))
            if positions:
                position = positions[0]

            if position is None:
                return OrderResult(success=False, error=f"Position {ticket} not found")

            order_type = mt5.ORDER_TYPE_SELL if position.type == 0 else mt5.ORDER_TYPE_BUY
            tick = mt5.symbol_info_tick(position.symbol)
            price = tick.bid if order_type == mt5.ORDER_TYPE_SELL else tick.ask
            vol = lot_size or position.volume

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": position.symbol,
                "volume": float(vol),
                "type": order_type,
                "position": int(ticket),
                "price": price,
                "deviation": 20,
                "magic": 123456,
                "comment": "Close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(request)
            success = result.retcode == mt5.TRADE_RETCODE_DONE

            return OrderResult(
                success=success,
                ticket=ticket,
                error=None if success else f"MT5 error {result.retcode}",
            )

        except Exception as e:
            logger.error(f"MT5 close_order error: {e}")
            return OrderResult(success=False, error=str(e))

    async def modify_order(
        self,
        ticket: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> OrderResult:
        if self.paper_mode or not MT5_AVAILABLE:
            return OrderResult(success=True, ticket=ticket)

        try:
            positions = mt5.positions_get(ticket=int(ticket))
            if not positions:
                return OrderResult(success=False, error=f"Position {ticket} not found")
            pos = positions[0]

            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": int(ticket),
                "symbol": pos.symbol,
                "sl": float(stop_loss) if stop_loss else pos.sl,
                "tp": float(take_profit) if take_profit else pos.tp,
            }

            result = mt5.order_send(request)
            success = result.retcode == mt5.TRADE_RETCODE_DONE
            return OrderResult(
                success=success,
                ticket=ticket,
                error=None if success else f"MT5 error {result.retcode}",
            )

        except Exception as e:
            logger.error(f"MT5 modify_order error: {e}")
            return OrderResult(success=False, error=str(e))

    async def get_open_orders(self) -> List[Dict]:
        if self.paper_mode or not MT5_AVAILABLE:
            return self._paper_account.orders

        try:
            positions = mt5.positions_get()
            if positions is None:
                return []
            return [
                {
                    "ticket": str(p.ticket),
                    "symbol": p.symbol,
                    "direction": "long" if p.type == 0 else "short",
                    "lot_size": p.volume,
                    "entry_price": p.price_open,
                    "current_price": p.price_current,
                    "stop_loss": p.sl,
                    "take_profit": p.tp,
                    "profit": p.profit,
                }
                for p in positions
            ]
        except Exception as e:
            logger.error(f"MT5 get_open_orders error: {e}")
            return []

    # --- Paper trading methods ---

    async def _place_paper_order(
        self,
        symbol: str,
        direction: str,
        lot_size: float,
        stop_loss: float,
        take_profit: float,
        comment: str,
    ) -> OrderResult:
        """Simulate order placement for paper trading."""
        tick = await self._get_simulated_tick(symbol)
        entry_price = tick.ask if direction == "long" else tick.bid if tick else 1.0

        ticket = self._paper_account.next_ticket()
        order = {
            "ticket": ticket,
            "symbol": symbol,
            "direction": direction,
            "lot_size": lot_size,
            "entry_price": entry_price,
            "current_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "profit": 0.0,
            "comment": comment,
        }
        self._paper_account.orders.append(order)

        logger.info(
            f"TRADE [PAPER] MT5: {symbol} {direction} {lot_size} lots "
            f"@ {entry_price:.5f} SL={stop_loss:.5f} TP={take_profit:.5f}"
        )

        return OrderResult(
            success=True,
            ticket=ticket,
            symbol=symbol,
            direction=direction,
            lot_size=lot_size,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    async def _close_paper_order(
        self,
        ticket: str,
        lot_size: Optional[float],
    ) -> OrderResult:
        """Simulate order close for paper trading."""
        order = next((o for o in self._paper_account.orders if o["ticket"] == ticket), None)
        if order:
            self._paper_account.orders.remove(order)
        return OrderResult(success=True, ticket=ticket)

    async def _get_simulated_tick(self, symbol: str) -> TickData:
        """Return a simulated tick (mid-price placeholder)."""
        return TickData(
            symbol=symbol, bid=1.0, ask=1.0001, last=1.0, spread=0.0001
        )

    async def _get_simulated_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        count: int,
    ) -> OHLCV:
        """
        Return empty OHLCV structure.
        Real historical data should be fed via data provider.
        """
        import numpy as np
        n = count
        dates = pd.date_range(end=pd.Timestamp.now(tz="UTC"), periods=n, freq="5min")
        price = 1.1000
        rng = np.random.default_rng(42)
        changes = rng.normal(0, 0.0002, n).cumsum()
        closes = price + changes
        df = pd.DataFrame({
            "time": dates,
            "open": closes - rng.uniform(0, 0.0005, n),
            "high": closes + rng.uniform(0, 0.001, n),
            "low": closes - rng.uniform(0, 0.001, n),
            "close": closes,
            "volume": rng.integers(100, 1000, n).astype(float),
        })
        return OHLCV(symbol=symbol, timeframe=timeframe, data=df)

    def _normalize_timeframe(self, tf: str) -> int:
        """Convert timeframe string to MT5 constant."""
        return MT5_TIMEFRAMES.get(tf.upper(), 5)
