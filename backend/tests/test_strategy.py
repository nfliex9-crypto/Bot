import pandas as pd

from app.services.strategy import LiquidityBOSPullbackStrategy


def test_strategy_generates_signal_for_bullish_sweep_bos_pullback() -> None:
    rows = []
    price = 100.0
    for idx in range(45):
        open_price = price
        high = price + 0.4
        low = price - 0.4
        close = price + 0.05
        rows.append({"open": open_price, "high": high, "low": low, "close": close, "volume": 1000 + idx})
        price += 0.05

    # Force a bullish liquidity sweep + BOS while keeping close near EMA.
    rows[-1] = {
        "open": 102.0,
        "high": 103.2,
        "low": 99.4,   # Sweeps below prior low
        "close": 102.8,  # Closes above recent highs (BOS)
        "volume": 2500,
    }
    frame = pd.DataFrame(rows)

    strategy = LiquidityBOSPullbackStrategy()
    signal = strategy.generate_signal(frame)
    assert signal is not None
    assert signal.side == "buy"
    assert signal.tp1 > signal.entry_price
