from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    project_name: str = "AI Automated Trading System"
    app_env: str = "development"
    api_v1_prefix: str = "/api"
    debug: bool = False
    enable_background_loop: bool = True
    loop_interval_seconds: int = 60
    paper_trading: bool = True

    database_url: str = "postgresql+psycopg2://trader:trader@postgres:5432/trading"

    risk_per_trade: float = 0.0075
    max_drawdown: float = 0.15
    max_trades_per_session: int = 3
    default_account_equity: float = 100000.0
    min_confidence_threshold: float = 0.6

    default_timeframe: str = "M15"
    candle_limit: int = 250
    ai_min_training_samples: int = 25

    forex_symbols: str = "EURUSD,GBPUSD,USDJPY"
    crypto_symbols: str = "BTCUSDT,ETHUSDT,SOLUSDT"

    mt5_login: str | None = None
    mt5_password: str | None = None
    mt5_server: str | None = None
    mt5_path: str | None = None

    binance_api_key: str | None = None
    binance_api_secret: str | None = None
    binance_base_url: str = "https://api.binance.com"

    allowed_cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:8080", "http://localhost:8000"]
    )

    @property
    def forex_symbol_list(self) -> list[str]:
        return [symbol.strip().upper() for symbol in self.forex_symbols.split(",") if symbol.strip()]

    @property
    def crypto_symbol_list(self) -> list[str]:
        return [symbol.strip().upper() for symbol in self.crypto_symbols.split(",") if symbol.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
