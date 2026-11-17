# Sentinel MT5 — Cloud Bridge (No Windows)

## Architecture

- **Sentinel web app:** isolated Vercel project; protected owner's UI, status, and configuration
- **MetaApi:** maintains the MT5 terminal connection in its managed cloud
- **Neon:** linked account metadata and AES-256-GCM encrypted MetaApi API token
- **Windows:** not required for this integration. The old Windows agent remains a legacy optional path, not used by the cloud UI.
- **Trading engine:** separate from the connection. Not yet running or connected to this cloud bridge.

## Connect from a phone or browser

1. Open https://app.metaapi.cloud/accounts and sign up or sign in.
2. Add an **MT5 Demo** account using MetaApi's own broker connection interface; deploy it there. (Do not enter the MT5 password into Sentinel.)
3. In MetaApi's account/API access area, copy the MetaApi API token authorized to read the connected account.
4. Open Sentinel → MT5 Cloud Bridge → **ربط مفتاح MetaApi**. Paste the token into the **website form**, not ChatGPT. It is verified against MetaApi, then encrypted server-side and never shown again.
5. Click **اكتشاف الحسابات** and choose your MT5 Demo account.
6. Click refresh. Only when the provider returns `ACCOUNT_TRADE_MODE_DEMO` and `connectionStatus=CONNECTED` will Sentinel show **VERIFIED DEMO**.

## Features implemented

- Discover provider-registered MT5 accounts via official MetaApi Provisioning API.
- Link/unlink an MT5 account without revealing the broker password to Sentinel.
- Verify the *actual account type* via official REST account-information endpoint, never the server name.
- Read Demo account balance/equity (only after broker type verified).
- Show the provider deployment and connection status.
- Client/server admin access controls with no public endpoint exposing account data.
- Encrypt MetaApi token in Neon using a separate server environment key.
- Invalidate stale connected status after 2 minutes without a fresh verification.
- Remove/rotate token from settings; linked entries persist but cannot refresh until token is restored.

## Provider API sources

- Account list: https://metaapi.cloud/docs/provisioning/api/account/readAccounts/
- Account state: https://metaapi.cloud/docs/provisioning/api/account/readAccount/
- Account information: https://metaapi.cloud/docs/client/restApi/api/readTradingTerminalState/readAccountInformation/

Endpoints are allowlisted; arbitrary upstream URLs cannot be supplied. Currently supports provider client regions new-york/vint-hill and london only. For unsupported regions, Sentinel reports `UNSUPPORTED_METAAPI_REGION` instead of fabricating a connection.

## Continuity / limitations

MetaApi hosts the MT5 terminal independently of the customer's laptop, but it is a third-party service subject to outages, account expiration, quotas, and pricing. A 100% uptime guarantee is not possible.

**Important:** A cloud account connection is not an actively running trading bot. Vercel serverless functions only run during requests; no continuous strategy loop, order placement, or MT5 execution engine has been attached. For unattended continuous trading, deploy a separately monitored worker (e.g. Railway) which uses an approved Demo-only MetaApi execution adapter and reliable order state reconciliation.

**Current cloud integration is READ ONLY.** The UI has no trade-creation endpoint. It does not silently trade on LIVE/REAL accounts.

## Environment

In the Sentinel Vercel project, protect these server-side secrets:

- `DATABASE_URL`
- `DASHBOARD_ACCESS_KEY`
- `MT5_CLOUD_ENCRYPTION_KEY` (32-byte key encoded in 64 hex characters)

Never commit them to GitHub or expose them in client HTML/JS.

## Testing

```sh
node --check sentinel-console/api/cloud.js
node --check sentinel-console/cloud-ui.js
node --test sentinel-console/tests/cloud.test.cjs
```

This tests the handler and crypto with mocks. Verification against an actual user's MetaApi account requires their own explicit credential connection in the site.
