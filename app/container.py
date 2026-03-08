from __future__ import annotations

from app.config import Settings
from app.execution.binance_executor import BinanceExecutor
from app.execution.mt5_executor import MT5Executor
from app.execution.paper_executor import PaperExecutor
from app.services.trade_service import TradeService
from app.services.trading_engine import TradingEngine


def build_engine(settings: Settings) -> TradingEngine:
    if settings.trading_mode == "paper":
        forex_executor = PaperExecutor()
        crypto_executor = PaperExecutor()
    else:
        if not (settings.mt5_login and settings.mt5_password and settings.mt5_server):
            raise RuntimeError("MT5 credentials are required in live mode.")
        if not (settings.binance_api_key and settings.binance_api_secret):
            raise RuntimeError("Binance credentials are required in live mode.")
        forex_executor = MT5Executor(
            login=settings.mt5_login,
            password=settings.mt5_password,
            server=settings.mt5_server,
            path=settings.mt5_path,
        )
        crypto_executor = BinanceExecutor(
            api_key=settings.binance_api_key,
            api_secret=settings.binance_api_secret,
            testnet=settings.binance_testnet,
        )

    trade_service = TradeService(
        executor_forex=forex_executor,
        executor_crypto=crypto_executor,
        mode=settings.trading_mode,
    )
    return TradingEngine(settings=settings, trade_service=trade_service)

