from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Automated Trading System"
    env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = "postgresql+psycopg2://trader:trader@localhost:5432/trading"

    trading_enabled: bool = False
    trade_loop_seconds: int = 60

    risk_per_trade: float = 0.0075
    max_drawdown: float = 0.15
    max_trades_per_session: int = 3
    atr_period: int = 14

    initial_equity: float = 100000.0

    ai_confidence_threshold: float = 0.55
    model_path: str = "app/models/random_forest.joblib"

    forex_symbols: str = "EURUSD,GBPUSD,USDJPY"
    crypto_symbols: str = "BTCUSDT,ETHUSDT"

    mt5_login: str | None = None
    mt5_password: str | None = None
    mt5_server: str | None = None
    mt5_path: str | None = None

    binance_api_key: str | None = None
    binance_api_secret: str | None = None
    binance_testnet: bool = True

    @property
    def forex_symbol_list(self) -> List[str]:
        return [s.strip() for s in self.forex_symbols.split(",") if s.strip()]

    @property
    def crypto_symbol_list(self) -> List[str]:
        return [s.strip() for s in self.crypto_symbols.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
