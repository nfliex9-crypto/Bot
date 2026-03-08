from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    trading_mode: Literal["paper", "live"] = Field(default="paper", alias="TRADING_MODE")
    database_url: str = Field(
        default="postgresql+psycopg2://postgres:postgres@db:5432/trading_bot",
        alias="DATABASE_URL",
    )

    account_balance: float = Field(default=3000.0, alias="ACCOUNT_BALANCE")
    risk_per_trade: float = Field(default=0.0075, alias="RISK_PER_TRADE")
    max_drawdown: float = Field(default=0.15, alias="MAX_DRAWDOWN")
    max_trades_per_session: int = Field(default=3, alias="MAX_TRADES_PER_SESSION")

    symbols_forex: str = Field(default="EURUSD,GBPUSD,USDJPY", alias="SYMBOLS_FOREX")
    symbols_crypto: str = Field(default="BTCUSDT,ETHUSDT", alias="SYMBOLS_CRYPTO")

    timeframe_bias: str = Field(default="H1", alias="TIMEFRAME_BIAS")
    timeframe_structure: str = Field(default="M15", alias="TIMEFRAME_STRUCTURE")
    timeframe_execution: str = Field(default="M5", alias="TIMEFRAME_EXECUTION")

    use_structure_stop: bool = Field(default=False, alias="USE_STRUCTURE_STOP")
    atr_period: int = Field(default=14, alias="ATR_PERIOD")
    atr_multiplier: float = Field(default=1.5, alias="ATR_MULTIPLIER")

    london_start_hour: int = Field(default=7, alias="LONDON_START_HOUR")
    london_end_hour: int = Field(default=16, alias="LONDON_END_HOUR")
    newyork_start_hour: int = Field(default=12, alias="NEWYORK_START_HOUR")
    newyork_end_hour: int = Field(default=21, alias="NEWYORK_END_HOUR")

    enable_news_filter: bool = Field(default=True, alias="ENABLE_NEWS_FILTER")
    news_lookahead_minutes: int = Field(default=45, alias="NEWS_LOOKAHEAD_MINUTES")
    news_api_url: str = Field(
        default="https://nfs.faireconomy.media/ff_calendar_thisweek.json",
        alias="NEWS_API_URL",
    )

    mt5_login: str | None = Field(default=None, alias="MT5_LOGIN")
    mt5_password: str | None = Field(default=None, alias="MT5_PASSWORD")
    mt5_server: str | None = Field(default=None, alias="MT5_SERVER")
    mt5_path: str | None = Field(default=None, alias="MT5_PATH")

    binance_api_key: str | None = Field(default=None, alias="BINANCE_API_KEY")
    binance_api_secret: str | None = Field(default=None, alias="BINANCE_API_SECRET")
    binance_testnet: bool = Field(default=True, alias="BINANCE_TESTNET")

    model_path: str = Field(default="artifacts/random_forest_model.joblib", alias="MODEL_PATH")
    scaler_path: str = Field(default="artifacts/feature_scaler.joblib", alias="SCALER_PATH")

    polling_seconds: int = Field(default=60, alias="POLLING_SECONDS")

    @property
    def forex_symbols(self) -> list[str]:
        return [s.strip().upper() for s in self.symbols_forex.split(",") if s.strip()]

    @property
    def crypto_symbols(self) -> list[str]:
        return [s.strip().upper() for s in self.symbols_crypto.split(",") if s.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

