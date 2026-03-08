from __future__ import annotations

import abc
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd

from core.models import Direction, Market, OpenTrade, TradeSignal
from utils.logger import get_logger

logger = get_logger(__name__)


class BaseExecutor(abc.ABC):
    """
    Abstract base class for all trade executors.

    Concrete implementations must handle the specifics of each
    broker/exchange API while sharing the same interface.
    """

    def __init__(self, market: Market, paper_mode: bool = True) -> None:
        self._market = market
        self._paper_mode = paper_mode
        self._connected = False

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    @abc.abstractmethod
    async def connect(self) -> bool:
        """Establish connection to broker/exchange. Returns success."""
        ...

    @abc.abstractmethod
    async def disconnect(self) -> None:
        """Cleanly close the connection."""
        ...

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------------
    # Account information
    # ------------------------------------------------------------------

    @abc.abstractmethod
    async def get_account_balance(self) -> float:
        """Returns the current free/available balance in account currency."""
        ...

    @abc.abstractmethod
    async def get_account_equity(self) -> float:
        """Returns the total equity including floating P&L."""
        ...

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    @abc.abstractmethod
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV bars.
        Returns DataFrame with columns: open, high, low, close, volume
        and a DatetimeIndex in UTC.
        """
        ...

    @abc.abstractmethod
    async def get_current_price(self, symbol: str) -> Tuple[float, float]:
        """Returns (bid, ask) for the given symbol."""
        ...

    # ------------------------------------------------------------------
    # Order management
    # ------------------------------------------------------------------

    @abc.abstractmethod
    async def place_order(self, signal: TradeSignal) -> Optional[str]:
        """
        Places a market order with SL and TP1 set.
        Returns broker order ID on success, None on failure.
        """
        ...

    @abc.abstractmethod
    async def modify_stop_loss(
        self, trade: OpenTrade, new_sl: float
    ) -> bool:
        """Moves the stop loss to a new price level."""
        ...

    @abc.abstractmethod
    async def close_partial(
        self, trade: OpenTrade, close_pct: float
    ) -> bool:
        """
        Closes a percentage of the position at market.
        E.g., close_pct=0.40 closes 40% of the position.
        """
        ...

    @abc.abstractmethod
    async def close_trade(self, trade: OpenTrade) -> bool:
        """Closes the entire remaining position at market."""
        ...

    @abc.abstractmethod
    async def get_open_trades(self) -> List[OpenTrade]:
        """Returns all currently open positions from the broker/exchange."""
        ...

    # ------------------------------------------------------------------
    # Paper trading helpers
    # ------------------------------------------------------------------

    def is_paper(self) -> bool:
        return self._paper_mode

    def log_order(self, action: str, symbol: str, details: Dict) -> None:
        mode = "PAPER" if self._paper_mode else "LIVE"
        logger.info("[%s] %s | %s | %s", mode, action, symbol, details)
