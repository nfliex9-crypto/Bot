-- Additive, research-only Edge Lab runs (never used to authorize broker orders).
-- Signals are scored on broker OHLC with observed P90 quote spread as a
-- *proxy*, explicitly not a reconstruction of historic execution prices.
CREATE TABLE IF NOT EXISTS sentinel_edge_lab_runs (
 id uuid PRIMARY KEY,
 account_id text NOT NULL,
 symbol text NOT NULL,
 timeframe text NOT NULL CHECK(timeframe='M15'),
 version text NOT NULL,
 dataset_last_bar timestamptz NOT NULL,
 evaluated_at timestamptz NOT NULL DEFAULT NOW(),
 report jsonb NOT NULL,
 UNIQUE(account_id,symbol,timeframe,version,dataset_last_bar)
);
CREATE INDEX IF NOT EXISTS sentinel_edge_lab_account_recent
 ON sentinel_edge_lab_runs(account_id,evaluated_at DESC);
