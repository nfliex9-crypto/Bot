from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class OrderResult:
    success: bool
    broker_ticket: Optional[str]
    executed_price: Optional[float]
    executed_qty: Optional[float]
    commission: float
    swap: float
    error: Optional[str]
    raw_response: Optional[dict] = None


@dataclass
class CloseResult:
    success: bool
    close_price: Optional[float]
    pnl: Optional[float]
    commission: float
    error: Optional[str]


class BaseExecutor(ABC):
    """Abstract base class for trade execution engines."""

    def __init__(self, name: str, paper_mode: bool = True):
        self.name = name
        self.paper_mode = paper_mode

    @abstractmethod
    async def open_trade(
        self,
        symbol: str,
        direction: str,
        lot_size: float,
        entry_price: Optional[float],
        stop_loss: float,
        tp1: float,
        comment: str = "AI_BOT",
    ) -> OrderResult: ...

    @abstractmethod
    async def close_trade(
        self,
        broker_ticket: str,
        symbol: str,
        lot_size: float,
        direction: str,
        close_price: Optional[float] = None,
    ) -> CloseResult: ...

    @abstractmethod
    async def modify_stop_loss(
        self,
        broker_ticket: str,
        symbol: str,
        new_stop_loss: float,
    ) -> bool: ...

    @abstractmethod
    async def get_open_positions(self) -> list: ...
