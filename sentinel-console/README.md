# Sentinel MT5 Control Center — Standalone / Isolated

## MT5 Demo — free cloud provider (default)

**TickerAll Free is the default provider**, not MetaApi. It offers up to five demo accounts at $0 according to https://tickerall.com/pricing. Setup happens from the Sentinel MT5 page with a TickerAll API key and optional one-time Demo broker credentials, no Windows. The API key is encrypted server-side; broker password is never persisted.

- GET `/api/free-mt5?action=status` returns sanitized provider demo account states.
- POST `saveKey`, `connect`, `inspect`, `disconnect`, and `forgetKey` require the owner's console key.
- No trade execution endpoints. No real-account access.
- The Free plan may cool a connection after idle; fully unattended 24/7 bot execution is **not enabled or guaranteed**.

See [CLOUD-MT5.md](./CLOUD-MT5.md) for provider-specific instructions.


Independent premium Arabic RTL web console for **nfliex9-crypto/Bot**. Does not import or alter the running MT5 bot. Deploy separately on Vercel.

## Actual capabilities
- Animated dashboard and equity chart; **sample mode visibly identified**.
- Secure server-side API gateway (GET dashboard/trades/signals/performance/model, POST control/training/backtest).
- Start/stop/pause/resume only when remote bot config explicitly says **paper** or **demo**, never live. Commands require confirmation.
- Local Strategy Draft editor with 13 strategies, thresholds and toggles; export JSON. **Drafts are not applied to the bot**, because current Bot API has no write endpoint for strategy parameters.
- Local CSV OHLC research backtest: EMA20/50, ATR stop and 2R target. Approximate bar-based simulation only.
- Remote backtest endpoint is labelled **SYNTHETIC**: current backend generates synthetic candles, so the result cannot be used as market-based evidence.
- AI training endpoint configured with synthetic_samples=0, requiring real saved trades.
- Event audit for this browser session; not MT5 Journal.
- No fake broker orders, no live-account API control.

## Environment (Vercel)
Set all in the private project's environment configuration:

```txt
DASHBOARD_ACCESS_KEY=<random secret of at least 24 characters>
BOT_API_URL=https://<private authenticated bot API host>  # optional until available
BOT_API_TOKEN=<server-to-server backend API token>         # optional, when backend verifies it
```

The front-end sends the dashboard key in an x-console-key header to its own Vercel function. The remote API URL and token are server-side only. **Never put MetaTrader account credentials into browser inputs or public environment variables.**

## Important security limits
The original Bot backend currently exposes permissive CORS and unauthenticated control APIs. Do NOT expose that backend directly on a public internet domain. Add backend authentication or private network access before linking. This console's authentication does not protect an otherwise public backend.

The original Linux MT5 connector may simulate prices and fills; do not mistake that for real MT5 Demo. Real MT5 Demo requires a Windows MT5 terminal and a connector with account-mode verification, including the separate `mt5-demo-isolation-2026-11-17` branch pending integration.

## Development
This is intentionally dependency-free HTML/CSS/JS with a Vercel Node serverless function. Static web files remain usable without backend connection.

```sh
python3 -m http.server 8000 --directory sentinel-console
```

The `/api/gateway` route requires Vercel serverless runtime.

## Honest feature status
- Preview, navigation, strategy draft, config export, CSV import & local test: **functional client-side**.
- Read and control APIs: **implemented gateway; require BOT_API_URL and account verification**.
- Actual MT5 Demo trade placement: **not enabled until Windows MT5 bridge and demo account are connected**.
- Real historical multi-strategy backtest and broker-level order modifications: **not implemented by existing backend**.

Project lives on GitHub branch `sentinel-console-isolated-v1` under `sentinel-console/`. This is deliberate isolation from `main` and any active bot.
