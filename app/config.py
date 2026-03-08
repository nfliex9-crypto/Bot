from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "AI Trading Bot System"
    environment: Literal["dev", "staging", "prod"] = "dev"
    log_level: str = "INFO"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/trading"

    mode: Literal["paper", "live"] = "paper"
    session_timezone: str = "UTC"
    polling_interval_seconds: int = 30
    auto_start_engine: bool = True
    symbols_forex: list[str] = Field(default_factory=lambda: ["EURUSD", "GBPUSD"])
    symbols_crypto: list[str] = Field(default_factory=lambda: ["BTCUSDT", "ETHUSDT"])

    # Risk profile
    account_balance: float = 3000.0
    risk_per_trade_pct: float = 0.75
    max_drawdown_pct: float = 15.0
    max_trades_per_session: int = 3

    # Trading management
    stop_type: Literal["atr", "structure"] = "atr"
    atr_period: int = 14
    atr_multiplier: float = 1.5
    news_block_window_minutes: int = 60

    # AI model
    model_path: str = "models/random_forest.joblib"
    min_confidence_to_trade: float = 0.55

    # MT5
    mt5_login: int | None = None
    mt5_password: str | None = None
    mt5_server: str | None = None
    mt5_path: str | None = None

    # Binance
    binance_api_key: str | None = None
    binance_api_secret: str | None = None
    binance_testnet: bool = True


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
