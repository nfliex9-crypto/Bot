from dataclasses import dataclass


@dataclass
class OrderRequest:
    symbol: str
    side: str
    quantity: float
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float


@dataclass
class OrderResult:
    success: bool
    order_id: str
    mode: str
    message: str = ""
