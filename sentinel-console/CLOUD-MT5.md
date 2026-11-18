# Sentinel — MT5 Demo Bridge, Zero Subscription

**Provider:** TickerAll Free (https://tickerall.com/pricing)

This is the default MT5 integration. It requires **no Windows laptop**, no MetaApi paid account, and no subscription for MT5 Demo under the provider's current published Free terms (up to 5 demo accounts).

## How to use

1. Sign up at https://tickerall.com/sign-up (Free plan; no card).
2. Open the **API keys** section inside your TickerAll dashboard and create an API key. For connecting broker sessions the key must have permission to create sessions; a provider read-only key may not support that operation.
3. In Sentinel, open **MT5 مجاني**, paste the TickerAll API key in the secure form. Sentinel validates it with TickerAll and saves only its AES-256-GCM encrypted copy in Neon.
4. Add a **DEMO MT5** account. Supply the broker server, demo login and demo password to the secure form. Sentinel forwards them to TickerAll once; it does not save the broker password. Alternatively connect your demo directly through the TickerAll dashboard and click Refresh in Sentinel.
5. See verified demo status and actual account data. LIVE accounts are blocked by Sentinel. Free-tier live API connections are also rejected by TickerAll according to their docs.

## Engineering

- Backend `api/free-mt5.js` only permits TickerAll `/v1/accounts`, `/v1/accounts/:id`, and `/v1/sessions`, with strict action allowlisting and private console authentication.
- Does **not** implement trade/close/modify endpoints, even for demo. The bridge reads account info, verifies Demo account type, and allows connecting/disconnecting demo sessions.
- API key is encrypted at rest using `MT5_CLOUD_ENCRYPTION_KEY`; no broker password persistence.
- Account balance/equity only appear after the provider confirms Demo.
- Provider is a **third party**. Its published free offer and account limits are not guaranteed to remain unchanged.
- The former MetaApi implementation remains in `api/cloud.js` but is **not loaded by the UI**. No MetaApi account or subscription is created by Sentinel.

## Important limitations

**Free Demo accounts are not equivalent to an always-hot 24/7 paid terminal.** The Free plan can cool an idle session; per TickerAll's docs the warm window lasts a limited time and you can reconnect by POST /v1/sessions. Because neither the provider on Free nor Sentinel stores the demo broker password, unattended rewarming may require re-entering credentials.

**The strategy engine is separate and still not deployed.** This account link alone does not automatically trade, run an EA, or guarantee uptime. Future continuous trading requires a worker service plus resilient idempotent execution with Demo-only safeguards; zero cost for a genuinely uninterrupted server is not guaranteed.

## Official source references

- https://tickerall.com/pricing
- https://tickerall.com/docs
- https://tickerall.com/faq

No MetaApi trial or Cloud-g2 plan is required. Ignore the paid MetaApi flow.
