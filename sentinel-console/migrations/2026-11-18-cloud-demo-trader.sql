-- Sentinel cloud DEMO: ledger, cycle monitoring, and a single-process lease.
-- Non-destructive additive tables, NO brokerage credentials or order API in Neon.
-- All broker order submission remains disabled unless local operator config gates pass.
CREATE TABLE IF NOT EXISTS sentinel_cloud_trader_lease (
  worker_name text PRIMARY KEY,
  lease_owner uuid NOT NULL,
  lease_until timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS sentinel_cloud_trader_daily (
  account_id text NOT NULL,
  utc_day text NOT NULL,
  start_equity numeric NOT NULL CHECK(start_equity>0),
  PRIMARY KEY(account_id,utc_day)
);
CREATE TABLE IF NOT EXISTS sentinel_cloud_trader_intents (
  account_id text NOT NULL,
  signal_hash text NOT NULL CHECK(signal_hash ~ '^[a-f0-9]{64}$'),
  symbol text NOT NULL,
  family text NOT NULL,
  side text NOT NULL CHECK(side IN ('LONG','SHORT')),
  bar_time timestamptz NOT NULL,
  comment text NOT NULL,
  status text NOT NULL,
  broker_ticket text,
  error_code text,
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW(),
  PRIMARY KEY(account_id,signal_hash)
);
CREATE INDEX IF NOT EXISTS sentinel_cloud_trader_intents_pending
  ON sentinel_cloud_trader_intents(account_id,status,created_at DESC);
CREATE TABLE IF NOT EXISTS sentinel_cloud_trader_cycles (
  cycle_id uuid PRIMARY KEY,
  account_id text,
  account_last4 text,
  mode text NOT NULL,
  status text NOT NULL,
  reason text NOT NULL,
  observations jsonb NOT NULL DEFAULT '[]'::jsonb,
  orders_sent integer NOT NULL DEFAULT 0 CHECK(orders_sent>=0),
  observed_at timestamptz NOT NULL DEFAULT NOW()
);

-- True completed broker round-trips only. Separate from orders, shadow signals
-- and speculative research. Commission may arrive after the initial close.
CREATE TABLE IF NOT EXISTS sentinel_cloud_trader_fills (
  account_id text NOT NULL,
  signal_hash text NOT NULL,
  broker_ticket text NOT NULL,
  symbol text NOT NULL,
  family text NOT NULL,
  close_time timestamptz NOT NULL,
  currency text NOT NULL,
  profit numeric NOT NULL,
  swap numeric NOT NULL,
  commission numeric NOT NULL,
  verified_at timestamptz NOT NULL DEFAULT NOW(),
  PRIMARY KEY(account_id,broker_ticket),
  FOREIGN KEY (account_id,signal_hash) REFERENCES sentinel_cloud_trader_intents(account_id,signal_hash)
);

-- Separately authorized, time-bounded, exact-account Fusion DEMO trial.
-- Server and masked account must match the connected broker roster.
CREATE TABLE IF NOT EXISTS sentinel_cloud_trader_authorizations (
  account_id text PRIMARY KEY,
  expected_last4 text NOT NULL CHECK(expected_last4 ~ '^[0-9]{4}$'),
  expected_server text NOT NULL,
  enabled boolean NOT NULL DEFAULT false,
  expires_at timestamptz NOT NULL,
  risk_pct numeric NOT NULL DEFAULT .25 CHECK(risk_pct>0 AND risk_pct<=.25),
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW()
);
