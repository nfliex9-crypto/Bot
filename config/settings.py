from __future__ import annotations

from functools import lru_cache
from typing import List, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Trading mode ──────────────────────────────────────────
    trading_mode: Literal["paper", "live"] = "paper"
    log_level: str = "INFO"

    # ── Account ───────────────────────────────────────────────
    account_balance: float = 3000.0
    risk_per_trade: float = 0.0075
    max_drawdown: float = 0.15
    max_trades_per_session: int = 3

    # ── Database ──────────────────────────────────────────────
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "trading"
    db_password: str = "trading_secret"
    db_name: str = "trading_bot"
    database_url: str = "postgresql+asyncpg://trading:trading_secret@localhost:5432/trading_bot"

    # ── Binance ───────────────────────────────────────────────
    binance_api_key: str = ""
    binance_api_secret: str = ""
    binance_testnet: bool = True

    # ── MetaTrader 5 ─────────────────────────────────────────
    mt5_login: int = 0
    mt5_password: str = ""
    mt5_server: str = ""
    mt5_path: str = ""

    # ── News API ──────────────────────────────────────────────
    news_api_key: str = ""
    news_api_url: str = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    news_buffer_minutes: int = 30

    # ── API Server ────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_secret_key: str = "change_this_to_a_long_random_secret"

    # ── Sessions ──────────────────────────────────────────────
    london_open_utc: str = "07:00"
    london_close_utc: str = "16:00"
    new_york_open_utc: str = "13:00"
    new_york_close_utc: str = "22:00"

    # ── Symbols ───────────────────────────────────────────────
    forex_symbols: str = "EURUSD,GBPUSD,USDJPY,AUDUSD,USDCAD"
    crypto_symbols: str = "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT"

    # ── Strategy parameters ───────────────────────────────────
    atr_period: int = 14
    atr_sl_multiplier: float = 1.5
    swing_lookback: int = 20
    liquidity_threshold: float = 0.001    # 0.1% sweep tolerance
    bos_confirmation_bars: int = 2
    pullback_fib_min: float = 0.382
    pullback_fib_max: float = 0.618
    min_rr_ratio: float = 1.5
    ai_confidence_threshold: float = 0.60

    # ── TP/SL ratios ──────────────────────────────────────────
    tp1_ratio: float = 1.0
    tp2_ratio: float = 1.5
    tp3_ratio: float = 2.0
    tp1_size_pct: float = 0.40   # 40% of position at TP1
    tp2_size_pct: float = 0.35   # 35% at TP2
    tp3_size_pct: float = 0.25   # 25% at TP3

    # ── Multi-timeframe ───────────────────────────────────────
    bias_timeframe: str = "1h"
    trend_timeframe: str = "15m"
    entry_timeframe: str = "5m"

    @property
    def forex_symbol_list(self) -> List[str]:
        return [s.strip() for s in self.forex_symbols.split(",") if s.strip()]

    @property
    def crypto_symbol_list(self) -> List[str]:
        return [s.strip() for s in self.crypto_symbols.split(",") if s.strip()]

    @property
    def is_live(self) -> bool:
        return self.trading_mode == "live"

    @property
    def is_paper(self) -> bool:
        return self.trading_mode == "paper"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
