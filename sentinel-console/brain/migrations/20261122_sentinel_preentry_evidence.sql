-- Sentinel V2 PRE-ENTRY EVIDENCE LEDGER
-- DEVELOPMENT ONLY. Do not apply to Neon until user approves a single release.
-- Purpose: trace the strategy + exact sizing risk BEFORE order submission.
-- No credentials, no broker orders, no destructive updates and no fabricated fills.
BEGIN;

ALTER TABLE sentinel_cloud_trader_intents
  ADD COLUMN IF NOT EXISTS decision_tagged_at timestamptz,
  ADD COLUMN IF NOT EXISTS risk_at_entry numeric(22,8),
  ADD COLUMN IF NOT EXISTS risk_pct_at_entry numeric(10,6),
  ADD COLUMN IF NOT EXISTS volume_at_entry numeric(22,8),
  ADD COLUMN IF NOT EXISTS stop_loss_at_entry numeric(22,8),
  ADD COLUMN IF NOT EXISTS take_profit_at_entry numeric(22,8),
  ADD COLUMN IF NOT EXISTS decision_version text,
  ADD COLUMN IF NOT EXISTS decision_snapshot jsonb;

ALTER TABLE sentinel_cloud_trader_fills
  ADD COLUMN IF NOT EXISTS open_time timestamptz,
  ADD COLUMN IF NOT EXISTS open_price numeric(22,8),
  ADD COLUMN IF NOT EXISTS close_price numeric(22,8);

-- Null means UNKNOWN, never coalesce to a fake risk/price/time.
ALTER TABLE sentinel_cloud_trader_intents
 ADD CONSTRAINT sentinel_intent_risk_positive_v2 CHECK
 (risk_at_entry IS NULL OR risk_at_entry > 0) NOT VALID;

-- Historical rows remain unchanged; validate separately before release.
CREATE INDEX IF NOT EXISTS sentinel_fills_evidence_v2_idx
 ON sentinel_cloud_trader_fills(account_id,signal_hash,open_time,close_time);

COMMIT;
