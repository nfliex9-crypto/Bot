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
  ADD COLUMN IF NOT EXISTS close_price numeric(22,8),
  ADD COLUMN IF NOT EXISTS broker_history_complete boolean;

-- Null means UNKNOWN, never coalesce to a fake risk/price/time.
DO $
BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='sentinel_intent_risk_positive_v2') THEN
  ALTER TABLE sentinel_cloud_trader_intents
   ADD CONSTRAINT sentinel_intent_risk_positive_v2
   CHECK (risk_at_entry IS NULL OR risk_at_entry > 0) NOT VALID;
 END IF;
END $;

-- Historical rows remain unchanged; validate separately before release.
CREATE INDEX IF NOT EXISTS sentinel_fills_evidence_v2_idx
 ON sentinel_cloud_trader_fills(account_id,signal_hash,open_time,close_time);

CREATE OR REPLACE VIEW sentinel_cloud_v2_evidence AS
SELECT f.account_id,f.broker_ticket,f.signal_hash,
 i.signal_hash AS intent_signal_hash,
 f.symbol,i.symbol AS intent_symbol,
 f.family,i.family AS intent_family,
 i.side,i.side AS intent_side,
 i.status AS execution_status,
 i.decision_version,
 CASE WHEN i.decision_tagged_at IS NOT NULL AND i.risk_at_entry>0
  THEN 'PREENTRY_RISK_RECORDED' ELSE 'UNKNOWN' END AS entry_status,
 f.broker_history_complete,
 i.decision_tagged_at,i.risk_at_entry,
 f.open_time,f.close_time,f.profit
FROM sentinel_cloud_trader_fills f
JOIN sentinel_cloud_trader_intents i
 ON i.account_id=f.account_id AND i.signal_hash=f.signal_hash
JOIN sentinel_cloud_trader_authorizations a ON a.account_id=f.account_id
WHERE a.expected_server ILIKE '%Fusion%Demo%';

COMMIT;
