from __future__ import annotations

from pathlib import Path

import polars as pl


def write_parquet(df: pl.DataFrame, path: str) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(output)
