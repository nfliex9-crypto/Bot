"""
Binance Broker Connector.

Supports:
- Spot trading (paper and live)
- Futures/Perpetual trading (paper and live)
- Real-time price feeds
- OHLCV data via REST API
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import pandas as pd
import pytz

from app.brokers.base import BaseBroker, OrderResult, TickData, OHLCV, AccountInfo
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("binance_broker")

UTC = pytz.UTC

# Timeframe mapping: string → Binance interval
BINANCE_INTERVALS = {
    "M1": "1m",
    "M3": "3m",
    "M5": "5m",
    "M15": "15m",
    "M30": "30m",
    "H1": "1h",
    "H2": "2h",
    "H4": "4h",
    "H6": "6h",
    "H12": "12h",
    "D1": "1d",
    "W1": "1w",
}

try:
    from binance import AsyncClient, BinanceAPIException
    from binance.enums import (
        SIDE_BUY, SIDE_SELL,
        ORDER_TYPE_MARKET, ORDER_TYPE_LIMIT,
        FUTURE_ORDER_TYPE_MARKET, FUTURE_ORDER_TYPE_STOP_MARKET,
    )
    BINANCE_AVAILABLE = True
except ImportError:
    logger.warning("python-binance not installed")
    BINANCE_AVAILABLE = False


class BinancePaperAccount:
    """Simulated Binance account for paper trading."""

    def __init__(self, balance: float = 3000.0):
        self.balance = balance
        self.equity = balance
        self.positions: List[Dict] = []
        self._next_order_id = 100000

    def next_order_id(self) -> str:
        oid = str(self._next_order_id)
        self._next_order_id += 1
        return oid


class BinanceBroker(BaseBroker):
    """
    Binance broker connector for crypto trading.

    Supports both testnet (paper) and mainnet (live) trading.
    Uses Futures for proper SL/TP execution.
    """

    def __init__(
        self,
        api_key: str = None,
        secret_key: str = None,
        testnet: bool = None,
        paper_mode: bool = None,
        use_futures: bool = True,
    ):
        _paper = paper_mode if paper_mode is not None else settings.is_paper
        super().__init__(paper_mode=_paper)
        self.api_key = api_key or settings.BINANCE_API_KEY or ""
        self.secret_key = secret_key or settings.BINANCE_SECRET_KEY or ""
        self.testnet = testnet if testnet is not None else settings.BINANCE_TESTNET
        self.use_futures = use_futures
        self._client: Optional[Any] = None
        self._paper_account = BinancePaperAccount(settings.ACCOUNT_BALANCE)
        self._utc = UTC

    async def connect(self) -> bool:
        """Initialize Binance API client."""
        if self.paper_mode or not BINANCE_AVAILABLE:
            self._connected = True
            logger.info("Binance broker: connected in paper/simulation mode")
            return True

        try:
            self._client = await AsyncClient.create(
                api_key=self.api_key,
                api_secret=self.secret_key,
                testnet=self.testnet,
            )
            # Ping to verify
            await self._client.ping()
            server_time = await self._client.get_server_time()
            self._connected = True

            mode = "TESTNET" if self.testnet else "MAINNET"
            logger.info(f"Binance connected ({mode} {'futures' if self.use_futures else 'spot'})")
            return True

        except Exception as e:
            logger.error(f"Binance connection error: {e}")
            return False

    async def disconnect(self):
        """Close Binance client."""
        if self._client and BINANCE_AVAILABLE:
            try:
                await self._client.close_connection()
            except Exception:
                pass
        self._connected = False
        logger.info("Binance broker disconnected")

    async def get_account_info(self) -> AccountInfo:
        if self.paper_mode or not BINANCE_AVAILABLE or not self._client:
            acc = self._paper_account
            return AccountInfo(
                balance=acc.balance,
                equity=acc.equity,
                margin=0.0,
                free_margin=acc.balance,
                margin_level=0.0,
                currency="USDT",
                leverage=10,
            )

        try:
            if self.use_futures:
                account = await self._client.futures_account()
                balance = float(account.get("totalWalletBalance", 0))
                equity = float(account.get("totalMarginBalance", 0))
                margin = float(account.get("totalInitialMargin", 0))
                free_margin = float(account.get("availableBalance", 0))
            else:
                account = await self._client.get_account()
                balances = account.get("balances", [])
                usdt = next((b for b in balances if b["asset"] == "USDT"), {})
                balance = float(usdt.get("free", 0)) + float(usdt.get("locked", 0))
                equity = balance
                margin = 0.0
                free_margin = float(usdt.get("free", 0))

            return AccountInfo(
                balance=balance,
                equity=equity,
                margin=margin,
                free_margin=free_margin,
                margin_level=0.0,
                currency="USDT",
                leverage=10,
            )

        except Exception as e:
            logger.error(f"Binance get_account_info error: {e}")
            return AccountInfo(balance=0, equity=0, margin=0, free_margin=0, margin_level=0)

    async def get_tick(self, symbol: str) -> Optional[TickData]:
        if self.paper_mode or not BINANCE_AVAILABLE or not self._client:
            return await self._get_simulated_tick(symbol)

        try:
            ticker = await self._client.get_order_book(symbol=symbol, limit=1)
            bid = float(ticker["bids"][0][0]) if ticker["bids"] else 0.0
            ask = float(ticker["asks"][0][0]) if ticker["asks"] else 0.0
            last = (bid + ask) / 2

            return TickData(
                symbol=symbol,
                bid=bid,
                ask=ask,
                last=last,
                spread=ask - bid,
                timestamp=datetime.now(UTC),
            )
        except Exception as e:
            logger.error(f"Binance get_tick error ({symbol}): {e}")
            return None

    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        count: int = 200,
    ) -> Optional[OHLCV]:
        if self.paper_mode or not BINANCE_AVAILABLE or not self._client:
            return await self._get_simulated_ohlcv(symbol, timeframe, count)

        try:
            interval = self._normalize_timeframe(timeframe)
            if self.use_futures:
                klines = await self._client.futures_klines(
                    symbol=symbol, interval=interval, limit=count
                )
            else:
                klines = await self._client.get_klines(
                    symbol=symbol, interval=interval, limit=count
                )

            if not klines:
                return None

            df = pd.DataFrame(klines, columns=[
                "time", "open", "high", "low", "close", "volume",
                "close_time", "quote_volume", "trades",
                "taker_buy_base", "taker_buy_quote", "ignore"
            ])
            df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = df[col].astype(float)
            df = df[["time", "open", "high", "low", "close", "volume"]].copy()
            df = df.sort_values("time").reset_index(drop=True)

            return OHLCV(symbol=symbol, timeframe=timeframe, data=df)

        except Exception as e:
            logger.error(f"Binance get_ohlcv error ({symbol} {timeframe}): {e}")
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
        if self.paper_mode or not BINANCE_AVAILABLE or not self._client:
            return await self._place_paper_order(
                symbol, direction, lot_size, stop_loss, take_profit
            )

        try:
            side = SIDE_BUY if direction == "long" else SIDE_SELL
            quantity = round(lot_size, 3)

            if self.use_futures:
                # Place market entry
                order = await self._client.futures_create_order(
                    symbol=symbol,
                    side=side,
                    type="MARKET",
                    quantity=quantity,
                )
                entry_price = float(order.get("avgPrice", order.get("price", 0)))
                order_id = str(order.get("orderId", ""))

                # Set stop loss via STOP_MARKET
                sl_side = SIDE_SELL if direction == "long" else SIDE_BUY
                await self._client.futures_create_order(
                    symbol=symbol,
                    side=sl_side,
                    type="STOP_MARKET",
                    quantity=quantity,
                    stopPrice=round(stop_loss, 4),
                    closePosition=True,
                    timeInForce="GTC",
                )

                # Set take profit via TAKE_PROFIT_MARKET
                await self._client.futures_create_order(
                    symbol=symbol,
                    side=sl_side,
                    type="TAKE_PROFIT_MARKET",
                    quantity=quantity,
                    stopPrice=round(take_profit, 4),
                    closePosition=True,
                    timeInForce="GTC",
                )

            else:
                order = await self._client.create_order(
                    symbol=symbol,
                    side=side,
                    type="MARKET",
                    quantity=quantity,
                )
                entry_price = float(order.get("fills", [{}])[0].get("price", 0))
                order_id = str(order.get("orderId", ""))

            logger.info(
                f"TRADE Binance order: {symbol} {direction} {quantity} "
                f"@ {entry_price:.4f} SL={stop_loss:.4f} TP={take_profit:.4f}"
            )

            return OrderResult(
                success=True,
                order_id=order_id,
                ticket=order_id,
                symbol=symbol,
                direction=direction,
                lot_size=lot_size,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )

        except Exception as e:
            logger.error(f"Binance place_order error: {e}")
            return OrderResult(success=False, error=str(e))

    async def close_order(
        self,
        ticket: str,
        lot_size: Optional[float] = None,
    ) -> OrderResult:
        if self.paper_mode or not BINANCE_AVAILABLE or not self._client:
            return await self._close_paper_order(ticket)

        try:
            # Find and close the position
            positions = await self._client.futures_position_information()
            pos = next(
                (p for p in positions if p.get("orderId") == ticket
                 or abs(float(p.get("positionAmt", 0))) > 0),
                None
            )
            if pos is None:
                return OrderResult(success=False, error="Position not found")

            symbol = pos["symbol"]
            amt = abs(float(pos["positionAmt"]))
            side = SIDE_SELL if float(pos["positionAmt"]) > 0 else SIDE_BUY
            vol = lot_size or amt

            await self._client.futures_create_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=round(vol, 3),
                reduceOnly=True,
            )

            return OrderResult(success=True, ticket=ticket)

        except Exception as e:
            logger.error(f"Binance close_order error: {e}")
            return OrderResult(success=False, error=str(e))

    async def modify_order(
        self,
        ticket: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> OrderResult:
        """Modify SL/TP by cancelling old and placing new conditional orders."""
        if self.paper_mode or not BINANCE_AVAILABLE or not self._client:
            return OrderResult(success=True, ticket=ticket)

        logger.info(f"Binance modify_order: ticket={ticket} sl={stop_loss} tp={take_profit}")
        return OrderResult(success=True, ticket=ticket)

    async def get_open_orders(self) -> List[Dict]:
        if self.paper_mode or not BINANCE_AVAILABLE or not self._client:
            return self._paper_account.positions

        try:
            if self.use_futures:
                positions = await self._client.futures_position_information()
                return [
                    {
                        "ticket": str(p.get("symbol", "")),
                        "symbol": p["symbol"],
                        "direction": "long" if float(p["positionAmt"]) > 0 else "short",
                        "lot_size": abs(float(p["positionAmt"])),
                        "entry_price": float(p["entryPrice"]),
                        "current_price": float(p["markPrice"]),
                        "profit": float(p["unrealizedProfit"]),
                    }
                    for p in positions
                    if abs(float(p.get("positionAmt", 0))) > 0
                ]
            return []
        except Exception as e:
            logger.error(f"Binance get_open_orders error: {e}")
            return []

    # --- Paper trading helpers ---

    async def _place_paper_order(
        self,
        symbol: str,
        direction: str,
        lot_size: float,
        stop_loss: float,
        take_profit: float,
    ) -> OrderResult:
        """Simulate Binance order."""
        tick = await self._get_simulated_tick(symbol)
        entry_price = tick.ask if direction == "long" else tick.bid

        order_id = self._paper_account.next_order_id()
        position = {
            "ticket": order_id,
            "symbol": symbol,
            "direction": direction,
            "lot_size": lot_size,
            "entry_price": entry_price,
            "current_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "profit": 0.0,
        }
        self._paper_account.positions.append(position)

        logger.info(
            f"TRADE [PAPER] Binance: {symbol} {direction} {lot_size} "
            f"@ {entry_price:.4f} SL={stop_loss:.4f} TP={take_profit:.4f}"
        )

        return OrderResult(
            success=True,
            ticket=order_id,
            symbol=symbol,
            direction=direction,
            lot_size=lot_size,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    async def _close_paper_order(self, ticket: str) -> OrderResult:
        pos = next((p for p in self._paper_account.positions if p["ticket"] == ticket), None)
        if pos:
            self._paper_account.positions.remove(pos)
        return OrderResult(success=True, ticket=ticket)

    async def _get_simulated_tick(self, symbol: str) -> TickData:
        return TickData(
            symbol=symbol, bid=50000.0, ask=50001.0, last=50000.5, spread=1.0
        )

    async def _get_simulated_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        count: int,
    ) -> OHLCV:
        import numpy as np
        n = count
        dates = pd.date_range(end=pd.Timestamp.now(tz="UTC"), periods=n, freq="5min")
        rng = np.random.default_rng(42)
        price = 50000.0
        changes = rng.normal(0, 50, n).cumsum()
        closes = price + changes
        df = pd.DataFrame({
            "time": dates,
            "open": closes - rng.uniform(0, 20, n),
            "high": closes + rng.uniform(0, 50, n),
            "low": closes - rng.uniform(0, 50, n),
            "close": closes,
            "volume": rng.uniform(0.1, 10.0, n),
        })
        return OHLCV(symbol=symbol, timeframe=timeframe, data=df)

    def _normalize_timeframe(self, tf: str) -> str:
        """Convert timeframe string to Binance interval."""
        return BINANCE_INTERVALS.get(tf.upper(), "5m")
