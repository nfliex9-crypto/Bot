from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List
from enum import Enum


class TradingMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Trading Mode ──────────────────────────────────────────────────────────
    trading_mode: TradingMode = TradingMode.PAPER

    # ── Account ───────────────────────────────────────────────────────────────
    account_balance: float = Field(default=3000.0, gt=0)
    risk_per_trade: float = Field(default=0.0075, gt=0, le=0.05)
    max_drawdown_pct: float = Field(default=0.15, gt=0, le=1.0)
    max_trades_per_session: int = Field(default=3, ge=1)

    # ── MetaTrader5 ───────────────────────────────────────────────────────────
    mt5_login: int = Field(default=0)
    mt5_password: str = Field(default="")
    mt5_server: str = Field(default="")
    mt5_path: str = Field(default="")
    mt5_symbols: str = Field(default="EURUSD,GBPUSD,USDJPY,AUDUSD,USDCAD,GBPJPY,EURJPY")

    @property
    def mt5_symbol_list(self) -> List[str]:
        return [s.strip() for s in self.mt5_symbols.split(",") if s.strip()]

    # ── Binance ───────────────────────────────────────────────────────────────
    binance_api_key: str = Field(default="")
    binance_secret_key: str = Field(default="")
    binance_testnet: bool = Field(default=True)
    binance_symbols: str = Field(default="BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,ADAUSDT")

    @property
    def binance_symbol_list(self) -> List[str]:
        return [s.strip() for s in self.binance_symbols.split(",") if s.strip()]

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://trader:securepassword@localhost:5432/trading_bot"
    )
    database_sync_url: str = Field(
        default="postgresql://trader:securepassword@localhost:5432/trading_bot"
    )

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379/0")

    # ── News Filter ───────────────────────────────────────────────────────────
    news_api_key: str = Field(default="")
    news_blackout_minutes: int = Field(default=30, ge=0)

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = Field(default="INFO")
    log_dir: str = Field(default="./logs")

    # ── API ───────────────────────────────────────────────────────────────────
    api_secret_key: str = Field(default="change_this_to_a_secure_random_string")
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)

    # ── Strategy Parameters ───────────────────────────────────────────────────
    # ATR period for stop loss
    atr_period: int = Field(default=14)
    atr_multiplier: float = Field(default=1.5)

    # Take profit R-multiples
    tp1_r: float = Field(default=1.0)
    tp2_r: float = Field(default=1.5)
    tp3_r: float = Field(default=2.0)

    # Minimum AI confidence to take a trade
    min_confidence: float = Field(default=0.60)

    # Timeframes
    htf_timeframe: str = Field(default="H1")
    mtf_timeframe: str = Field(default="M15")
    ltf_timeframe: str = Field(default="M5")

    # Swing lookback periods
    swing_lookback: int = Field(default=10)
    bos_lookback: int = Field(default=20)


settings = Settings()
