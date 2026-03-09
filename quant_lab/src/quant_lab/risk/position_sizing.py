from __future__ import annotations


def vol_target_position_size(
    capital: float,
    target_vol: float,
    asset_vol: float,
    max_leverage: float = 2.0,
) -> float:
    if asset_vol <= 1e-12:
        return 0.0
    notional = capital * (target_vol / asset_vol)
    cap = capital * max_leverage
    return max(-cap, min(cap, notional))
