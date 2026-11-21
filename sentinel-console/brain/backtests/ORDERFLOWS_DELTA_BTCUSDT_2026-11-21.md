# Sentinel | Orderflows Delta historical backtest | 2026-11-21

## Provenance

- Market: Binance Spot BTCUSDT; public daily aggTrades, taker side from isBuyerMaker (True => taker SELL, False => taker BUY).
- Dates: TRAIN 2026-10-20 to 2026-10-24; strictly later OOS 2026-11-13 to 2026-11-17.
- Verified official daily ZIP SHA256 CHECKSUM for every file. Total aggregated taker trade records: 12,081,050.
- Derived historical bars: M5=2880; M15=960.
- Source signal engine: Sentinel on isolated branch sentinel-orderflows-delta-curriculum-v1.
- Not the user's FusionMarkets MT5 account; shorts are synthetic research trades, not Binance Spot short fills.

## Hypotheses frozen before OOS

- Delta Surge: negative Delta then 3 increasingly positive candles, mirror short; four-bar illustrative example.
- Delta Divergence: tied/new 6-bar high with negative Delta SHORT; tied/new 6-bar low with positive Delta LONG. Equal-price tolerance zero.
- Delta Flips: prior intrabar MIN-dominant candle to current MAX-dominant (mirror short); 15% range tolerance, zero gap bars.
- Only closed-bar signals. Entry next candle open; stop 1.5x ATR14; target 2R; timeout 12 bars; worst-case stop if stop and target both hit.
- Max one open trade per strategy, hypothetical 0.25% equity risk/trade, no portfolio netting.
- Cost scenarios 8, 24, 40 bps round-trip including hypothetical fee/spread/slippage; not measured Fusion transaction costs.

## Complete results

| TF | Split | RT cost bps | Strategy | Trades | Win % | Avg net R | PF | Equity % | Max DD % |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|
| M5 | TRAIN | 8 | delta_surge | 36 | 36.11 | -0.5015 | 0.4617 | -4.435 | 4.961 |
| M5 | TRAIN | 8 | delta_divergence | 87 | 42.53 | -0.3306 | 0.5898 | -6.985 | 7.258 |
| M5 | TRAIN | 8 | delta_flips | 1 | 0 | -1.7578 | 0 | -0.439 | 0.439 |
| M5 | TRAIN | 24 | delta_surge | 36 | 22.22 | -1.6085 | 0.0674 | -13.523 | 13.523 |
| M5 | TRAIN | 24 | delta_divergence | 87 | 22.99 | -1.4177 | 0.0805 | -26.618 | 26.733 |
| M5 | TRAIN | 24 | delta_flips | 1 | 0 | -3.2733 | 0 | -0.818 | 0.818 |
| M5 | TRAIN | 40 | delta_surge | 36 | 5.56 | -2.7155 | 0.0176 | -21.773 | 21.773 |
| M5 | TRAIN | 40 | delta_divergence | 87 | 5.75 | -2.5049 | 0.0125 | -42.15 | 42.162 |
| M5 | TRAIN | 40 | delta_flips | 1 | 0 | -4.7888 | 0 | -1.197 | 1.197 |
| M5 | OOS | 8 | delta_surge | 27 | 18.52 | -0.7268 | 0.2354 | -4.8 | 5.192 |
| M5 | OOS | 8 | delta_divergence | 72 | 44.44 | -0.187 | 0.6956 | -3.34 | 4.86 |
| M5 | OOS | 8 | delta_flips | 1 | 0 | -1.2292 | 0 | -0.307 | 0.307 |
| M5 | OOS | 24 | delta_surge | 27 | 14.81 | -1.2442 | 0.1116 | -8.077 | 8.335 |
| M5 | OOS | 24 | delta_divergence | 72 | 27.78 | -0.6911 | 0.2619 | -11.734 | 12.356 |
| M5 | OOS | 24 | delta_flips | 1 | 0 | -1.6875 | 0 | -0.422 | 0.422 |
| M5 | OOS | 40 | delta_surge | 27 | 11.11 | -1.7615 | 0.0551 | -11.245 | 11.378 |
| M5 | OOS | 40 | delta_divergence | 72 | 18.06 | -1.1951 | 0.1059 | -19.409 | 19.821 |
| M5 | OOS | 40 | delta_flips | 1 | 0 | -2.1459 | 0 | -0.536 | 0.536 |
| M15 | TRAIN | 8 | delta_surge | 7 | 28.57 | -0.2618 | 0.4823 | -0.459 | 0.617 |
| M15 | TRAIN | 8 | delta_divergence | 27 | 25.93 | -0.4575 | 0.3747 | -3.051 | 3.349 |
| M15 | TRAIN | 8 | delta_flips | 2 | 50 | 0.6685 | 5.9612 | 0.334 | 0.067 |
| M15 | TRAIN | 24 | delta_surge | 7 | 14.29 | -0.7825 | 0.0998 | -1.363 | 1.363 |
| M15 | TRAIN | 24 | delta_divergence | 27 | 18.52 | -0.9988 | 0.146 | -6.538 | 6.538 |
| M15 | TRAIN | 24 | delta_flips | 2 | 50 | 0.0865 | 1.2679 | 0.043 | 0.162 |
| M15 | TRAIN | 40 | delta_surge | 7 | 0 | -1.3032 | 0 | -2.259 | 2.259 |
| M15 | TRAIN | 40 | delta_divergence | 27 | 14.81 | -1.5401 | 0.0629 | -9.903 | 9.903 |
| M15 | TRAIN | 40 | delta_flips | 2 | 50 | -0.4954 | 0.0313 | -0.248 | 0.256 |
| M15 | OOS | 8 | delta_surge | 9 | 33.33 | -0.2337 | 0.6567 | -0.528 | 1.522 |
| M15 | OOS | 8 | delta_divergence | 21 | 38.1 | -0.3229 | 0.5263 | -1.689 | 1.901 |
| M15 | OOS | 8 | delta_flips | 0 | n/a | n/a | n/a | 0 | 0 |
| M15 | OOS | 24 | delta_surge | 9 | 33.33 | -0.4618 | 0.4568 | -1.038 | 1.898 |
| M15 | OOS | 24 | delta_divergence | 21 | 33.33 | -0.587 | 0.3154 | -3.044 | 3.206 |
| M15 | OOS | 24 | delta_flips | 0 | n/a | n/a | n/a | 0 | 0 |
| M15 | OOS | 40 | delta_surge | 9 | 33.33 | -0.6898 | 0.3234 | -1.546 | 2.273 |
| M15 | OOS | 40 | delta_divergence | 21 | 33.33 | -0.851 | 0.183 | -4.382 | 4.494 |
| M15 | OOS | 40 | delta_flips | 0 | n/a | n/a | n/a | 0 | 0 |

## Interpretation & limitations

- All OOS Surge and Divergence results negative in both frames, even with low 8-bps scenario.
- Flips had one OOS M5 trade and zero OOS M15 trades; not statistically meaningful.
- Course examples do not specify all numeric thresholds; research parameter choices were documented before testing. This does not refute broader discretionary course teaching.
- Bar-level stop path ambiguous; same-bar stop and TP use stop first. No reconstructed true bid/ask, latency, borrow, funding, slippage or full L2.
- Binance aggTrades compress matched fills: intrabar Delta extrema are approximate at aggTrade granularity.
- Ten market days are insufficient to establish robust edge. BTCUSDT Spot is NOT XAUUSD or Fusion MT5 BTCUSD.
- Hypothetical per-family equity, not account PnL. No live or demo order execution. Existing bot unchanged.

## Archive audit - dates, records and official SHA256

- 2026-10-20 | 794,034 aggregated trades | SHA256 8bf47107d00b6a62148a99f5a62953d4b70f0ecd616b3b93ad957015cd8103bf | https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2026-10-20.zip
- 2026-10-21 | 803,525 aggregated trades | SHA256 3adefe0c3bf271513271bae56b68cfc02121503ef3c363285881552c9d911cfc | https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2026-10-21.zip
- 2026-10-22 | 945,791 aggregated trades | SHA256 9cac084b5e1456356429b2b318e60039a1082153e87f1b23150e1d6761a11e82 | https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2026-10-22.zip
- 2026-10-23 | 674,730 aggregated trades | SHA256 6cc56ad96e162ce75239efe8ee2a7bdd8fa8dd4eaf2dbeaa396c6e745c6b3a29 | https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2026-10-23.zip
- 2026-10-24 | 539,660 aggregated trades | SHA256 ef6728f99972572d10982d711889ae84a38ab952920c6dd88e3a358da7ab8997 | https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2026-10-24.zip
- 2026-11-13 | 1,661,562 aggregated trades | SHA256 6ae5dd30ea0679f577a68ef448460eccf3cc5e771adf47a83f22e916e1e60aef | https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2026-11-13.zip
- 2026-11-14 | 2,219,759 aggregated trades | SHA256 cfcebbd9d5265850c2af512ae199daeb9fdc79c2cb8df99f4ab402e1b50e7fe1 | https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2026-11-14.zip
- 2026-11-15 | 2,026,448 aggregated trades | SHA256 41db65e5114cc0970d30878bfa24e13444066b16f5895391ba85c86cc679dee0 | https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2026-11-15.zip
- 2026-11-16 | 1,158,508 aggregated trades | SHA256 f9cd5440694f4211b3cbe6ebcaa35760473e39f4af95b0d77ff26759ee409257 | https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2026-11-16.zip
- 2026-11-17 | 1,257,033 aggregated trades | SHA256 96a78e941d30c864955f3dbc8bb6fbb6145f2cf28c8c5e4965a33c25abb3ddf1 | https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2026-11-17.zip

## References

- Official data documentation: https://github.com/binance/binance-public-data/blob/master/README.md
- Sentinel source code: https://github.com/nfliex9-crypto/Bot/blob/sentinel-orderflows-delta-curriculum-v1/sentinel-console/worker/orderflow/delta-engine.js
