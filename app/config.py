from functools import lru_cache
from typing import List, Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ai-trading-bot"
    env: Literal["dev", "prod", "test"] = "dev"
    log_level: str = "INFO"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    postgres_dsn: str = "postgresql+psycopg2://trader:trader@db:5432/trading"

    trading_mode: Literal["paper", "live"] = "paper"
    polling_seconds: int = 60

    account_balance: float = 3000.0
    risk_per_trade: float = 0.0075
    max_drawdown: float = 0.15
    max_trades_per_session: int = 3

    stop_loss_mode: Literal["atr", "structure"] = "atr"
    atr_period: int = 14
    atr_multiplier: float = 1.5
    structure_padding: float = 0.0002

    tp1_r_multiple: float = 1.0
    tp2_r_multiple: float = 1.5
    tp3_r_multiple: float = 2.0

    session_london_start: int = 7
    session_london_end: int = 17
    session_newyork_start: int = 8
    session_newyork_end: int = 17

    news_filter_enabled: bool = True
    news_cooldown_minutes: int = 30
    news_api_url: str = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    high_impact_only: bool = True

    forex_symbols: List[str] = Field(default_factory=lambda: ["EURUSD", "GBPUSD"])
    crypto_symbols: List[str] = Field(default_factory=lambda: ["BTCUSDT", "ETHUSDT"])

    mt5_login: Optional[int] = None
    mt5_password: Optional[str] = None
    mt5_server: Optional[str] = None
    mt5_path: Optional[str] = None

    binance_api_key: Optional[str] = None
    binance_api_secret: Optional[str] = None
    binance_testnet: bool = False

    model_path: str = "models/random_forest.joblib"
    min_training_samples: int = 50
    min_confidence_to_trade: float = 0.55


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

