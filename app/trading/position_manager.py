from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass(slots=True)
class ManagedPosition:
    symbol: str
    market: str
    side: Literal["buy", "sell"]
    entry: float
    stop_loss: float
    take_profits: list[float]
    quantity: float
    opened_at: datetime
    hit_tp: list[bool] = field(default_factory=lambda: [False, False, False])
    moved_to_be: bool = False


class PositionManager:
    def __init__(self) -> None:
        self.positions: dict[str, ManagedPosition] = {}

    def _key(self, symbol: str, market: str) -> str:
        return f"{market}:{symbol}"

    @staticmethod
    def build_take_profits(entry: float, stop_loss: float, side: Literal["buy", "sell"]) -> list[float]:
        risk = abs(entry - stop_loss)
        if side == "buy":
            return [entry + risk, entry + risk * 1.5, entry + risk * 2.0]
        return [entry - risk, entry - risk * 1.5, entry - risk * 2.0]

    def add(self, position: ManagedPosition) -> None:
        self.positions[self._key(position.symbol, position.market)] = position

    def active_count(self) -> int:
        return len(self.positions)

    def on_price(self, symbol: str, market: str, price: float) -> ManagedPosition | None:
        key = self._key(symbol, market)
        position = self.positions.get(key)
        if position is None:
            return None

        tps = position.take_profits
        if position.side == "buy":
            if price >= tps[0]:
                position.hit_tp[0] = True
            if price >= tps[1]:
                position.hit_tp[1] = True
            if price >= tps[2]:
                position.hit_tp[2] = True
            if price <= position.stop_loss:
                self.positions.pop(key, None)
        else:
            if price <= tps[0]:
                position.hit_tp[0] = True
            if price <= tps[1]:
                position.hit_tp[1] = True
            if price <= tps[2]:
                position.hit_tp[2] = True
            if price >= position.stop_loss:
                self.positions.pop(key, None)

        if position.hit_tp[0] and not position.moved_to_be:
            position.stop_loss = position.entry
            position.moved_to_be = True

        if all(position.hit_tp):
            self.positions.pop(key, None)
        return position
