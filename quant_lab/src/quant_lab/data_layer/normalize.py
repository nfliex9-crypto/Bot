from __future__ import annotations

import polars as pl


REQUIRED_COLUMNS = ["timestamp", "symbol", "open", "high", "low", "close", "volume"]


def normalize_ohlcv(df: pl.DataFrame) -> pl.DataFrame:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required OHLCV columns: {missing}")

    out = (
        df.with_columns(
            [
                pl.col("timestamp").cast(pl.Datetime).alias("timestamp"),
                pl.col("symbol").cast(pl.Utf8),
                pl.col("open").cast(pl.Float64),
                pl.col("high").cast(pl.Float64),
                pl.col("low").cast(pl.Float64),
                pl.col("close").cast(pl.Float64),
                pl.col("volume").cast(pl.Float64),
            ]
        )
        .sort(["symbol", "timestamp"])
        .with_columns(pl.col("close").pct_change().over("symbol").fill_null(0.0).alias("ret_1"))
    )
    return out
