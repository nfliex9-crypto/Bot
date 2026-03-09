from __future__ import annotations

import polars as pl


class FeatureFactory:
    def __init__(self, ret_col: str = "ret_1") -> None:
        self.ret_col = ret_col

    def build(self, df: pl.DataFrame) -> pl.DataFrame:
        windows = [3, 5, 10, 20, 50]
        out = df.sort(["symbol", "timestamp"])

        for w in windows:
            out = out.with_columns(
                [
                    pl.col(self.ret_col).rolling_mean(w).over("symbol").alias(f"ret_mean_{w}"),
                    pl.col(self.ret_col).rolling_std(w).over("symbol").alias(f"ret_std_{w}"),
                    pl.col(self.ret_col).rolling_skew(w).over("symbol").alias(f"ret_skew_{w}"),
                    pl.col("volume").rolling_mean(w).over("symbol").alias(f"vol_mean_{w}"),
                ]
            )

        out = out.with_columns(
            [
                ((pl.col("high") - pl.col("low")) / pl.col("close")).alias("hl_spread"),
                pl.col(self.ret_col).abs().rolling_mean(20).over("symbol").alias("absret_20"),
                (pl.col(self.ret_col).rolling_std(20).over("symbol") * (252**0.5)).alias("rv_20_ann"),
                (pl.col("ret_mean_5") - pl.col("ret_mean_20")).alias("alpha_1"),
                (pl.col("ret_mean_3") - pl.col("ret_mean_10")).alias("alpha_1_v2"),
                (pl.col("ret_mean_10") - pl.col("ret_mean_50")).alias("alpha_1_v3"),
                (pl.col("ret_std_5") - pl.col("ret_std_20")).alias("alpha_vol_spread_1"),
                (pl.col("ret_mean_5") / (pl.col("ret_std_20") + 1e-9)).alias("alpha_sharpe_like_1"),
            ]
        )

        out = out.with_columns(
            pl.when(pl.col("rv_20_ann") > pl.col("rv_20_ann").rolling_mean(60).over("symbol"))
            .then(pl.lit(1))
            .otherwise(pl.lit(0))
            .alias("regime_high_vol")
        )

        cross = (
            out.group_by("timestamp")
            .agg(pl.col(self.ret_col).mean().alias("market_ret"))
            .sort("timestamp")
        )
        out = out.join(cross, on="timestamp", how="left")
        out = out.with_columns((pl.col(self.ret_col) - pl.col("market_ret")).alias("ret_idio"))

        return out
