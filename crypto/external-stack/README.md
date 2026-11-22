# Sentinel Crypto Intelligence — verified upstream adapters

**Mode:** independent research / live market DATA only. **MT5 untouched.**
The external data and order-book engines are not rewritten or forked. The only local code is a source-integrity witness, adapter configuration and tests.

## Approved upstream versions

| Component | Exact version | Role | State |
| --- | --- | --- | --- |
| [Cryptofeed](https://github.com/bmoscon/cryptofeed/tree/v3.0.5) | `3.0.5` | Public exchange trade/L2 streams; official PCAP recorder | Configured; remote live verification pending |
| [NautilusTrader](https://github.com/nautechsystems/nautilus_trader/tree/v2.0.0rc9) | `2.0.0rc9` **research pre-release** | Official Kraken Spot DataTester + native managed order book | Configured read-only; hosted adapter test pending |
| [Bookmap](https://bookmap.com/knowledgebase/docs/API) | Licensed product | External heatmap/chart reference | Not connected; requires entitled API/data |
| [DeepCharts / DeepDOM](https://www.deepcharts.com/helpcenter/deepdom/article/installation-and-first-configuration) | Licensed product | Visual footprint/DOM review | Not connected; outbound API unverified |

> The upstream Cryptofeed package is AGPL-3.0-or-later. NautilusTrader is LGPL-3.0. Validate applicable license obligations before any commercial network use or redistribution.

## Genuine Kraken Spot BTC-USD test

Prerequisites: Python **3.13**, exchange connectivity, a clock synced to UTC. No API key, real-money permission or connected MT5 account.

```bash
python -m venv .venv
source .venv/bin/activate     # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r crypto/external-stack/requirements.txt
python crypto/external-stack/verify_live.py --exchange KRAKEN --symbol BTC-USD --seconds 60
```

Other permitted research pairs: `ETH-USD`, `SOL-USD` on Kraken; `BTC-USDT`, `ETH-USDT`, `SOL-USDT` on Binance Spot.

Expected output is one strict JSON line. `VERIFIED_RECENT_EXTERNAL_EVENTS` **only** means that both Cryptofeed callbacks provided fresh, properly labeled public trade and top-of-book data within that run. It does NOT prove any historical profitability, spot shorting, account connectivity, persistent uptime, or executable fills. Missing/stale/inconsistent trade or book events yield `DATA_UNVERIFIED` and a nonzero exit status.

Kraken's upstream adapter manages the L2 book and validates the venue's checksum by default. The witness uses max_depth=10 and checks event timestamps, positive quantities, non-crossed BBO, exact exchange/symbol attribution and timestamps. No local home-built order book or order-placement client exists.

## Capture real exchange WebSocket messages (official upstream utility)

```bash
git clone --depth 1 --branch v3.0.5 https://github.com/bmoscon/cryptofeed.git upstream-cryptofeed
python upstream-cryptofeed/examples/record.py KRAKEN BTC-USD --duration 60 --out ./captures/
```

This is the upstream **PCAP recorder**, not our implementation. It subscribes to `TRADES` and `L2_BOOK` by default, captures source frames and metadata, and requires a connected network. PCAP is not an independently verified backtest or permission to auto-trade. Protect captured records and use bounded retention.

## Read-only NautilusTrader official adapter

Pinned to v2.0.0rc9; the latest 2.x API is incompatible with stable 1.x. Install separately from the Cryptofeed environment if dependencies conflict:

```bash
python -m pip install -r crypto/external-stack/requirements-nautilus.txt
python crypto/external-stack/nautilus_kraken_spot.py
```

The script is a minimally adapted version of [upstream's data-only Kraken example](https://github.com/nautechsystems/nautilus_trader/blob/v2.0.0rc9/examples/live/kraken/data_tester.py): `KrakenProductType.SPOT`, `BTC/USD.KRAKEN`, public quotes, public trades, managed L2 book. **No execution client is registered, no strategy is deployed, no order route exists.** The node runs until stopped manually. `Environment.LIVE` refers to the **market-data environment**, not a funded account.

**Not for live-money production:** NautilusTrader 2.0.0rc9 is a release candidate; first validate compatibility and feed quality, then perform real historical/OOS and paper tests.

## Local deterministic tests (not live feed evidence)

```bash
python -m unittest discover -s crypto/external-stack -p 'test_*.py' -v
python -m py_compile crypto/external-stack/verify_live.py crypto/external-stack/nautilus_kraken_spot.py
```

The tests exercise missing data, bad timestamps, wrong venue, incorrect book, malformed prices, allowed symbol scope, and the impossibility of enabling order execution via this component.

## GitHub Actions

- [Crypto public external feed](../../.github/workflows/crypto-external-feed.yml): contract tests, genuine Kraken websocket observation and official upstream PCAP capture.
- [NautilusTrader adapter smoke](../../.github/workflows/crypto-nautilus-check.yml): exact upstream v2.0.0rc9 package installation and **build data-only node**; does not start execution.
- Workflow files existing is NOT proof any Action completed. Check jobs/logs/artifacts before claiming a verified live feed. CI jobs use only public market data and do not receive broker keys.

## Next gate

1. Run/check both GitHub Actions jobs and resolve failures.
2. Record independent valid Kraken public L2 + Trades capture, preserve source metadata.
3. Validate NautilusTrader's managed native OrderBook on the same venue/instrument and benchmark repeatability.
4. Implement a paper-only strategy adapter **using NautilusTrader's official simulation primitives**, after genuine event replay. Never promote the unverified Delta strategy ideas as live profitable.
5. Before any 24/7 deployment, specify resource sizing, explicit record retention, network monitoring and a separately managed service. Never reuse MT5 credentials or service identity.
