from abc import ABC, abstractmethod
from typing import Optional
import pandas as pd


class BaseMarketConnector(ABC):
    """Abstract base class for all market connectors."""

    @abstractmethod
    async def connect(self) -> bool:
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        pass

    @abstractmethod
    async def get_ohlcv(
        self, symbol: str, timeframe: str, count: int = 500
    ) -> pd.DataFrame:
        pass

    @abstractmethod
    async def get_current_price(self, symbol: str) -> dict:
        pass

    @abstractmethod
    async def place_market_order(
        self,
        symbol: str,
        side: str,
        volume: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        comment: str = "",
    ) -> dict:
        pass

    @abstractmethod
    async def place_limit_order(
        self,
        symbol: str,
        side: str,
        price: float,
        volume: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        comment: str = "",
    ) -> dict:
        pass

    @abstractmethod
    async def modify_order(
        self,
        order_id: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> dict:
        pass

    @abstractmethod
    async def close_position(self, order_id: str, volume: Optional[float] = None) -> dict:
        pass

    @abstractmethod
    async def get_account_info(self) -> dict:
        pass

    @abstractmethod
    async def get_open_positions(self) -> list:
        pass
