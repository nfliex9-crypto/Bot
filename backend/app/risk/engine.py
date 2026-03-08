from dataclasses import dataclass

import pandas as pd


@dataclass
class RiskPlan:
    quantity: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    risk_amount: float


class RiskEngine:
    def __init__(self, risk_per_trade: float, max_drawdown: float, max_trades_per_session: int, atr_period: int):
        self.risk_per_trade = risk_per_trade
        self.max_drawdown = max_drawdown
        self.max_trades_per_session = max_trades_per_session
        self.atr_period = atr_period

    def calculate_atr(self, candles: pd.DataFrame) -> float:
        high_low = candles["high"] - candles["low"]
        high_close = (candles["high"] - candles["close"].shift(1)).abs()
        low_close = (candles["low"] - candles["close"].shift(1)).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(self.atr_period).mean().iloc[-1]
        if pd.isna(atr):
            atr = tr.tail(self.atr_period).mean()
        return float(max(atr, 1e-8))

    def can_trade(self, session_trade_count: int, drawdown: float) -> tuple[bool, str]:
        if drawdown >= self.max_drawdown:
            return False, "max_drawdown_reached"
        if session_trade_count >= self.max_trades_per_session:
            return False, "max_trades_per_session_reached"
        return True, "ok"

    def build_trade_plan(self, side: str, entry_price: float, account_equity: float, candles: pd.DataFrame) -> RiskPlan:
        atr = self.calculate_atr(candles)
        stop_distance = atr * 1.5
        risk_amount = account_equity * self.risk_per_trade
        quantity = risk_amount / stop_distance

        if side == "BUY":
            stop_loss = entry_price - stop_distance
            tp1 = entry_price + stop_distance
            tp2 = entry_price + stop_distance * 2
            tp3 = entry_price + stop_distance * 3
        else:
            stop_loss = entry_price + stop_distance
            tp1 = entry_price - stop_distance
            tp2 = entry_price - stop_distance * 2
            tp3 = entry_price - stop_distance * 3

        return RiskPlan(
            quantity=float(max(quantity, 0.0)),
            stop_loss=float(stop_loss),
            tp1=float(tp1),
            tp2=float(tp2),
            tp3=float(tp3),
            risk_amount=float(risk_amount),
        )

    def break_even_stop(self, side: str, entry_price: float, current_stop: float, current_price: float, tp1: float) -> float:
        tp1_hit = current_price >= tp1 if side == "BUY" else current_price <= tp1
        if tp1_hit:
            return entry_price
        return current_stop
