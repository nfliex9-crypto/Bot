from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from .adapters.base import MarketDataAdapter
from .normalize import normalize_ohlcv
from .quality import run_data_quality_checks
from .storage import write_parquet


@dataclass
class IngestConfig:
    symbols: list[str]
    start: str
    end: str
    interval: str
    out_path: str


def ingest_ohlcv(adapter: MarketDataAdapter, cfg: IngestConfig) -> pl.DataFrame:
    parts: list[pl.DataFrame] = []
    for symbol in cfg.symbols:
        df = adapter.fetch_ohlcv(symbol, cfg.start, cfg.end, cfg.interval)
        if df.is_empty():
            continue
        parts.append(df.with_columns(pl.lit(symbol).alias("symbol")))

    if not parts:
        raise ValueError("No OHLCV data returned from adapter.")

    merged = pl.concat(parts, how="vertical")
    normalized = normalize_ohlcv(merged)
    run_data_quality_checks(normalized)
    write_parquet(normalized, cfg.out_path)
    return normalized
