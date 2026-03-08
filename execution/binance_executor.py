from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import pandas as pd

from config.settings import settings
from core.models import Direction, Market, OpenTrade, TradeSignal, TradeStatus
from execution.base_executor import BaseExecutor
from utils.logger import get_logger

logger = get_logger(__name__)

try:
    from binance.client import Client as BinanceClient
    from binance.exceptions import BinanceAPIException
    BINANCE_AVAILABLE = True
except ImportError:
    BinanceClient = None
    BinanceAPIException = Exception
    BINANCE_AVAILABLE = False
    logger.warning("python-binance not available — Binance executor running in mock mode")


_TF_MAP = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
}


class PaperBinanceStore:
    """In-memory paper trade store for Binance."""

    def __init__(self) -> None:
        self._trades: Dict[str, OpenTrade] = {}
        self._balance: float = settings.account_balance

    def add_trade(self, trade: OpenTrade) -> None:
        self._trades[trade.trade_id] = trade

    def get_open_trades(self) -> List[OpenTrade]:
        return [t for t in self._trades.values() if t.status == TradeStatus.OPEN]

    @property
    def balance(self) -> float:
        return self._balance

    def equity(self, prices: Dict[str, float]) -> float:
        pnl = 0.0
        for t in self._trades.values():
            if t.status == TradeStatus.OPEN and t.symbol in prices:
                cp = prices[t.symbol]
                sl_dist = abs(t.entry_price - t.stop_loss)
                qty = t.lot_size
                if t.direction == Direction.LONG:
                    pnl += (cp - t.entry_price) * qty
                else:
                    pnl += (t.entry_price - cp) * qty
        return self._balance + pnl


class BinanceExecutor(BaseExecutor):
    """
    Binance Futures / Spot executor.

    Paper mode: simulates orders against an in-memory store.
    Live mode:  executes real Futures orders (USDT-margined).
    """

    def __init__(self) -> None:
        super().__init__(market=Market.CRYPTO, paper_mode=settings.is_paper)
        self._client: Optional[BinanceClient] = None
        self._paper_store = PaperBinanceStore()

    # ------------------------------------------------------------------
    async def connect(self) -> bool:
        if self._paper_mode or not BINANCE_AVAILABLE:
            logger.info("Binance Executor: connected in PAPER mode")
            self._connected = True
            return True

        loop = asyncio.get_event_loop()
        try:
            self._client = await loop.run_in_executor(
                None,
                lambda: BinanceClient(
                    settings.binance_api_key,
                    settings.binance_api_secret,
                    testnet=settings.binance_testnet,
                ),
            )
            # Verify connectivity
            await loop.run_in_executor(None, self._client.ping)
            self._connected = True
            logger.info(
                "Binance Executor: connected (testnet=%s)", settings.binance_testnet
            )
            return True
        except Exception as exc:
            logger.error("Binance connection failed: %s", exc)
            return False

    async def disconnect(self) -> None:
        self._client = None
        self._connected = False
        logger.info("Binance Executor: disconnected")

    # ------------------------------------------------------------------
    async def get_account_balance(self) -> float:
        if self._paper_mode or not BINANCE_AVAILABLE or not self._client:
            return self._paper_store.balance
        loop = asyncio.get_event_loop()
        try:
            account = await loop.run_in_executor(None, self._client.futures_account_balance)
            for asset in account:
                if asset["asset"] == "USDT":
                    return float(asset["balance"])
        except Exception as exc:
            logger.error("Binance balance fetch failed: %s", exc)
        return settings.account_balance

    async def get_account_equity(self) -> float:
        if self._paper_mode or not BINANCE_AVAILABLE or not self._client:
            return self._paper_store.balance
        loop = asyncio.get_event_loop()
        try:
            info = await loop.run_in_executor(None, self._client.futures_account)
            return float(info.get("totalWalletBalance", settings.account_balance))
        except Exception as exc:
            logger.error("Binance equity fetch failed: %s", exc)
        return settings.account_balance

    # ------------------------------------------------------------------
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
    ) -> pd.DataFrame:
        if self._paper_mode or not BINANCE_AVAILABLE or not self._client:
            return self._generate_mock_ohlcv(symbol, timeframe, limit)

        tf = _TF_MAP.get(timeframe, "5m")
        loop = asyncio.get_event_loop()
        try:
            klines = await loop.run_in_executor(
                None,
                lambda: self._client.futures_klines(
                    symbol=symbol, interval=tf, limit=limit
                ),
            )
            return self._parse_klines(klines)
        except Exception as exc:
            logger.error("Binance klines fetch failed for %s %s: %s", symbol, timeframe, exc)
            return pd.DataFrame()

    async def get_current_price(self, symbol: str) -> Tuple[float, float]:
        if self._paper_mode or not BINANCE_AVAILABLE or not self._client:
            return (50000.0, 50001.0)
        loop = asyncio.get_event_loop()
        try:
            ticker = await loop.run_in_executor(
                None, lambda: self._client.futures_orderbook_ticker(symbol=symbol)
            )
            return (float(ticker["bidPrice"]), float(ticker["askPrice"]))
        except Exception as exc:
            logger.error("Binance price fetch failed: %s", exc)
            return (0.0, 0.0)

    # ------------------------------------------------------------------
    async def place_order(self, signal: TradeSignal) -> Optional[str]:
        self.log_order(
            "PLACE",
            signal.symbol,
            {
                "direction": signal.direction.value,
                "entry": signal.entry_price,
                "sl": signal.stop_loss,
                "tp1": signal.tp1,
                "qty": signal.lot_size,
                "confidence": signal.ai_confidence,
            },
        )

        if self._paper_mode or not BINANCE_AVAILABLE or not self._client:
            return self._paper_place_order(signal)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._live_place_order(signal))

    def _paper_place_order(self, signal: TradeSignal) -> str:
        trade = OpenTrade(
            trade_id=signal.trade_id,
            symbol=signal.symbol,
            market=signal.market,
            direction=signal.direction,
            entry_price=signal.entry_price,
            current_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            tp1=signal.tp1,
            tp2=signal.tp2,
            tp3=signal.tp3,
            lot_size=signal.lot_size,
            risk_amount=signal.risk_amount,
            opened_at=datetime.now(timezone.utc),
            broker_order_id=f"PAPER_{signal.trade_id}",
        )
        self._paper_store.add_trade(trade)
        return trade.broker_order_id  # type: ignore[return-value]

    def _live_place_order(self, signal: TradeSignal) -> Optional[str]:
        side = "BUY" if signal.direction == Direction.LONG else "SELL"
        try:
            # Main market order
            order = self._client.futures_create_order(
                symbol=signal.symbol,
                side=side,
                type="MARKET",
                quantity=signal.lot_size,
            )
            order_id = str(order["orderId"])

            # Stop-loss order
            sl_side = "SELL" if signal.direction == Direction.LONG else "BUY"
            self._client.futures_create_order(
                symbol=signal.symbol,
                side=sl_side,
                type="STOP_MARKET",
                stopPrice=round(signal.stop_loss, 2),
                closePosition=True,
            )

            # Take-profit 1 (partial)
            tp1_qty = round(signal.lot_size * settings.tp1_size_pct, 4)
            self._client.futures_create_order(
                symbol=signal.symbol,
                side=sl_side,
                type="TAKE_PROFIT_MARKET",
                stopPrice=round(signal.tp1, 2),
                quantity=tp1_qty,
            )

            return order_id
        except BinanceAPIException as exc:
            logger.error("Binance order failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    async def modify_stop_loss(self, trade: OpenTrade, new_sl: float) -> bool:
        self.log_order("MODIFY_SL", trade.symbol, {"order": trade.broker_order_id, "new_sl": new_sl})
        if self._paper_mode or not BINANCE_AVAILABLE or not self._client:
            if trade.trade_id in self._paper_store._trades:
                self._paper_store._trades[trade.trade_id].stop_loss = new_sl
            return True
        loop = asyncio.get_event_loop()
        try:
            # Cancel existing SL and place new one
            side = "SELL" if trade.direction == Direction.LONG else "BUY"
            await loop.run_in_executor(
                None,
                lambda: self._client.futures_cancel_all_open_orders(symbol=trade.symbol),
            )
            await loop.run_in_executor(
                None,
                lambda: self._client.futures_create_order(
                    symbol=trade.symbol,
                    side=side,
                    type="STOP_MARKET",
                    stopPrice=round(new_sl, 2),
                    closePosition=True,
                ),
            )
            return True
        except Exception as exc:
            logger.error("Binance SL modification failed: %s", exc)
            return False

    async def close_partial(self, trade: OpenTrade, close_pct: float) -> bool:
        close_qty = round(trade.lot_size * close_pct, 4)
        self.log_order("PARTIAL_CLOSE", trade.symbol, {"qty": close_qty, "pct": close_pct})
        if self._paper_mode or not BINANCE_AVAILABLE or not self._client:
            return True
        side = "SELL" if trade.direction == Direction.LONG else "BUY"
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: self._client.futures_create_order(
                    symbol=trade.symbol,
                    side=side,
                    type="MARKET",
                    quantity=close_qty,
                    reduceOnly=True,
                ),
            )
            return True
        except Exception as exc:
            logger.error("Binance partial close failed: %s", exc)
            return False

    async def close_trade(self, trade: OpenTrade) -> bool:
        self.log_order("CLOSE", trade.symbol, {"order": trade.broker_order_id})
        if self._paper_mode or not BINANCE_AVAILABLE or not self._client:
            if trade.trade_id in self._paper_store._trades:
                self._paper_store._trades[trade.trade_id].status = TradeStatus.CLOSED
            return True
        side = "SELL" if trade.direction == Direction.LONG else "BUY"
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: self._client.futures_create_order(
                    symbol=trade.symbol,
                    side=side,
                    type="MARKET",
                    quantity=trade.lot_size,
                    reduceOnly=True,
                ),
            )
            return True
        except Exception as exc:
            logger.error("Binance close failed: %s", exc)
            return False

    async def get_open_trades(self) -> List[OpenTrade]:
        if self._paper_mode or not BINANCE_AVAILABLE or not self._client:
            return self._paper_store.get_open_trades()
        loop = asyncio.get_event_loop()
        try:
            positions = await loop.run_in_executor(
                None, self._client.futures_position_information
            )
            result = []
            for pos in positions:
                qty = float(pos.get("positionAmt", 0))
                if qty == 0:
                    continue
                direction = Direction.LONG if qty > 0 else Direction.SHORT
                entry = float(pos.get("entryPrice", 0))
                result.append(
                    OpenTrade(
                        trade_id=pos.get("symbol", ""),
                        symbol=pos.get("symbol", ""),
                        market=Market.CRYPTO,
                        direction=direction,
                        entry_price=entry,
                        current_price=float(pos.get("markPrice", entry)),
                        stop_loss=0.0,
                        tp1=0.0,
                        tp2=0.0,
                        tp3=0.0,
                        lot_size=abs(qty),
                        risk_amount=0.0,
                        opened_at=datetime.now(timezone.utc),
                        unrealised_pnl=float(pos.get("unrealizedProfit", 0)),
                    )
                )
            return result
        except Exception as exc:
            logger.error("Binance open trades fetch failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    @staticmethod
    def _parse_klines(klines: list) -> pd.DataFrame:
        df = pd.DataFrame(
            klines,
            columns=[
                "timestamp", "open", "high", "low", "close", "volume",
                "close_time", "quote_vol", "n_trades", "taker_buy_vol",
                "taker_buy_quote_vol", "ignore",
            ],
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.set_index("timestamp")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        return df[["open", "high", "low", "close", "volume"]].sort_index()

    @staticmethod
    def _generate_mock_ohlcv(symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        import numpy as np
        np.random.seed(hash(symbol + timeframe) % 2**31)
        freq_map = {"5m": "5min", "15m": "15min", "1h": "1h"}
        freq = freq_map.get(timeframe, "5min")
        dates = pd.date_range(end=pd.Timestamp.utcnow(), periods=limit, freq=freq, tz="UTC")
        base = 50000.0 if "BTC" in symbol else 3000.0
        close = base + np.cumsum(np.random.randn(limit) * base * 0.001)
        spread = base * 0.0005
        high = close + np.abs(np.random.randn(limit)) * spread
        low = close - np.abs(np.random.randn(limit)) * spread
        open_ = close + np.random.randn(limit) * spread * 0.5
        volume = np.random.uniform(10, 500, size=limit)
        df = pd.DataFrame(
            {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
            index=dates,
        )
        return df.sort_index()
