from __future__ import annotations

import polars as pl


def run_data_quality_checks(df: pl.DataFrame) -> None:
    if df.is_empty():
        raise ValueError("Data quality failed: empty DataFrame")

    null_counts = df.null_count().row(0)
    if any(v > 0 for v in null_counts):
        raise ValueError(f"Data quality failed: null values found {null_counts}")

    dupes = df.select(pl.struct(["timestamp", "symbol"]).is_duplicated().sum()).item()
    if dupes > 0:
        raise ValueError(f"Data quality failed: duplicate symbol/timestamp rows = {dupes}")

    bad_price_rows = df.filter(
        (pl.col("open") <= 0) | (pl.col("high") <= 0) | (pl.col("low") <= 0) | (pl.col("close") <= 0)
    ).height
    if bad_price_rows > 0:
        raise ValueError(f"Data quality failed: non-positive prices rows = {bad_price_rows}")
