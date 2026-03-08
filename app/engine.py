"""Trading engine orchestrator: strategies, AI, filters, execution."""
from datetime import datetime, timezone
import pandas as pd

from config import settings
from app.core.models import TradeSignal, MarketType
from app.core.strategy import run_all_strategies
from app.core.risk_manager import RiskManager
from app.ai.classifier import TradeClassifier
from app.filters.combined import all_filters_passed
from app.execution.mt5_executor import MT5Executor
from app.execution.binance_executor import BinanceExecutor
from app.database.session import SessionLocal
from app.database.models import Trade


# Symbol config: (symbol, market_type)
FOREX_SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
CRYPTO_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]


class TradingEngine:
    """Main trading engine - runs 24/7."""

    def __init__(self):
        self.risk_manager = RiskManager()
        self.classifier = TradeClassifier()
        self.mt5 = MT5Executor()
        self.binance = BinanceExecutor()
        self.paper = settings.TRADING_MODE == "paper"
        self._classifier_loaded = self.classifier.load()

    def _get_executor(self, market_type: MarketType):
        if market_type == MarketType.FOREX:
            return self.mt5
        return self.binance

    def _get_ohlcv(self, symbol: str, market_type: MarketType) -> tuple[pd.DataFrame | None, pd.DataFrame | None, pd.DataFrame | None]:
        ex = self._get_executor(market_type)
        h1 = ex.get_ohlcv(symbol, "H1", 100)
        m15 = ex.get_ohlcv(symbol, "M15", 100)
        m5 = ex.get_ohlcv(symbol, "M5", 100)
        return h1, m15, m5

    def run_cycle(self) -> list[dict]:
        """
        Run one analysis cycle. Returns list of executed trade info.
        """
        results = []

        # Filters
        passed, reasons = all_filters_passed()
        if not passed:
            return [{"status": "filtered", "reasons": reasons}]

        # Connect executors
        if not self.mt5.connect() and settings.MT5_LOGIN:
            pass  # MT5 optional
        if not self.binance.connect() and settings.BINANCE_API_KEY:
            pass  # Binance optional

        # Reset session at start of London
        now = datetime.now(timezone.utc)
        if now.hour == 8 and now.minute < 5:
            self.risk_manager.reset_session()

        # Update balance
        balance = settings.ACCOUNT_BALANCE
        if self.mt5._connected:
            balance = self.mt5.get_balance(self.paper)
        elif self.binance._connected:
            balance = self.binance.get_balance(self.paper)
        self.risk_manager.update_balance(balance)

        can_trade, msg = self.risk_manager.can_trade()
        if not can_trade:
            return [{"status": "risk_limit", "message": msg}]

        # Scan symbols
        for symbol, market_type in [(s, MarketType.FOREX) for s in FOREX_SYMBOLS] + [(s, MarketType.CRYPTO) for s in CRYPTO_SYMBOLS]:
            h1, m15, m5 = self._get_ohlcv(symbol, market_type)
            if h1 is None or m15 is None or m5 is None:
                continue

            signals = run_all_strategies(h1, m15, m5, symbol, market_type)
            for sig in signals:
                # AI confidence
                conf = self.classifier.score_signal(
                    h1, m15, m5, sig.direction.value, sig.strategy.value
                )
                sig.confidence = conf

                if conf < 0.6:
                    continue

                size, risk = self.risk_manager.position_size(
                    sig.entry_price, sig.stop_loss, sig.direction.value, confidence=conf
                )
                if size <= 0:
                    continue

                ex = self._get_executor(market_type)
                order_id = ex.place_order(sig, size, self.paper)
                if order_id:
                    self.risk_manager.record_trade()
                    db = SessionLocal()
                    try:
                        trade = Trade(
                            order_id=order_id,
                            symbol=sig.symbol,
                            direction=sig.direction.value,
                            strategy=sig.strategy.value,
                            entry_price=sig.entry_price,
                            stop_loss=sig.stop_loss,
                            tp1=sig.tp1, tp2=sig.tp2, tp3=sig.tp3,
                            size=size,
                            confidence=conf,
                            market_type=sig.market_type.value,
                            paper=self.paper,
                            status="open",
                        )
                        db.add(trade)
                        db.commit()
                        results.append({"status": "executed", "order_id": order_id, "symbol": symbol})
                    finally:
                        db.close()

        self.mt5.disconnect()
        self.binance.disconnect()
        return results if results else [{"status": "no_signals"}]
