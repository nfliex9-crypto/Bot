# Sentinel Crypto — external-first market data (2026-11-22)

## Core policy

This is an **external-first integration**, not another home-built crypto exchange gateway, order book, or heatmap. The existing MT5 bot is independent and must not be changed. No new live order authorization, credentials, databases or trading permissions are introduced.

| Responsibility | Approved upstream | Version / restrictions |
|---|---|---|
| Market-data callbacks & live normalized trades/depth | [bmoscon/cryptofeed](https://github.com/bmoscon/cryptofeed) | **3.0.5**, Python 3.13+; official WebSocket venue adapters |
| Recording market data for deterministic replay | Cryptofeed's official `examples/record.py` | PCAP output with connection metadata; **no custom collector** |
| Order-book construction, exchange adapters, event replay & future execution | [NautilusTrader](https://nautilustrader.io/docs/latest/) | Upstream 2.0 release candidate API; installation and example must be matched to the pinned version before use |
| Bookmap liquidity visualization / review | [Bookmap](https://bookmap.com/knowledgebase/docs/API) | Official Add-ons API; requires user's app and entitled exchange data |
| DeepCharts / DeepDOM review | [DeepCharts](https://www.deepcharts.com/helpcenter/deepdom/article/installation-and-first-configuration) | External Level 2 feed and license; an outbound machine data API for use by Sentinel is **not verified** |
| Alternative automated market execution | [Hummingbot](https://hummingbot.org/exchanges/) | Research alternative, not concurrent with Nautilus execution. Only one executor may own an account. |

### First actual data source

Start with **Kraken Spot BTC-USD** as venue-scoped market-data research. Kraken Spot is not a crypto perpetual exchange and is not evidence of legal permission to short. Optional independent reference: Binance Spot BTC-USDT, **not a consolidated/global book and not a proxy for Kraken BTC-USD fills**.

### Run upstream's official PCAP capture (no accounts, no artificial prices)

Linux/macOS/Windows with Python >=3.13 and a network connection to the exchange:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install 'cryptofeed==3.0.5'
git clone --depth 1 --branch v3.0.5 https://github.com/bmoscon/cryptofeed.git upstream-cryptofeed
python upstream-cryptofeed/examples/record.py KRAKEN BTC-USD --duration 60 --out ./captures/
```

On Windows PowerShell use `.venv\Scripts\Activate.ps1` instead of `source`.

Official repo's `record.py` subscribes to both TRADES and L2_BOOK by default. This data is exchange-originated; if the connection fails the recording does not fabricate candles, trades, or positions. PCAP **records upstream transport traffic**, not a ready-to-trade, validated historical L2 simulation.

An external feed witness (read-only, no trading, no private keys):

```bash
python crypto/external-stack/verify_live.py --exchange KRAKEN --symbol BTC-USD --seconds 45
# optionally: --exchange BINANCE --symbol BTC-USDT
```

Exit 0 means current run observed valid order book and executed-trade callbacks for that exact venue and pair, not that 24/7 availability has been proven. Exit nonzero means DATA_UNVERIFIED. No callbacks -> no data.

### Implementation boundaries

- We don't implement custom depth sequencing, trading venue adapters, maker/taker side inference, or heatmap. Use upstream implementations under version-pinned contracts.
- Cryptofeed `OrderBook` and `Trade` types are venue-normalized; public callbacks are not proof of account access or executable liquidity elsewhere.
- `verify_live.py` is only a small operational readiness witness. It observes source events; it does not calculate trading signals, make orders, or impersonate Bookmap.
- Order-flow lessons and strategy validation remain research-only until separately evaluated on real, authenticated source data.
- No secrets are needed to read public Kraken book/trade streams. Never commit exchange API keys.
- This development branch does **not** deploy a service, and Github-hosted runners cannot establish your own broker account is trading.
- Before a persistent 24/7 service: specify storage volume/retention, upstream recording rotation, connectivity alarms, bounded resource use, and approved region-specific venue access.
- Before any **real orders**: separate explicit authorization, authenticated account and exchange product suitability, settlement and order reconciliation, stop and sizing validation, tested emergency disablement.

### References

- Cryptofeed repository & docs: https://github.com/bmoscon/cryptofeed
- Cryptofeed official PCAP capture script: https://github.com/bmoscon/cryptofeed/blob/v3.0.5/examples/record.py
- Cryptofeed release: https://github.com/bmoscon/cryptofeed/releases/tag/v3.0.5
- NautilusTrader Binance: https://nautilustrader.io/docs/latest/integrations/binance/
- NautilusTrader book model: https://nautilustrader.io/docs/latest/concepts/order_book/
- Bookmap API: https://bookmap.com/knowledgebase/docs/API
- DeepDOM data requirements: https://www.deepcharts.com/helpcenter/deepdom/article/installation-and-first-configuration
