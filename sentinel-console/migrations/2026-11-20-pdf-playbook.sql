-- Sentinel research-only PDF Playbook outcomes, never broker approval records.
CREATE TABLE IF NOT EXISTS sentinel_pdf_playbook_runs (
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
CREATE INDEX IF NOT EXISTS sentinel_pdf_playbook_recent
 ON sentinel_pdf_playbook_runs(account_id,evaluated_at DESC);
