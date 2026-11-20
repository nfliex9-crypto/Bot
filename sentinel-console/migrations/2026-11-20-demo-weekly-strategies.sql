-- Verified-source weekly Demo strategy allocations, immutable per review week.
-- Sunday has closed: new UTC Monday snapshot on next scheduled worker cycle.
-- Changes only candidate priority (0 pause, 1 explore, 2 reward); never risk sizing.
CREATE TABLE IF NOT EXISTS sentinel_cloud_strategy_weekly (
 account_id text NOT NULL,
 symbol text NOT NULL,
 family text NOT NULL CHECK (family IN ('pdf_sweep_bos','pdf_fvg_retest')),
 week_start date NOT NULL,
 status text NOT NULL CHECK(status IN
  ('PAUSED_LOSING','REWARDED_PRIORITY','ACTIVE_NEUTRAL','WATCH_NEGATIVE','COLLECTING')),
 priority smallint NOT NULL CHECK(priority IN (0,1,2)),
 week_trades int NOT NULL CHECK (week_trades>=0),
 week_net numeric NOT NULL,
 rolling_trades int NOT NULL CHECK (rolling_trades>=0),
 rolling_net numeric NOT NULL,
 evidence jsonb NOT NULL,
 evaluated_at timestamptz NOT NULL DEFAULT NOW(),
 PRIMARY KEY(account_id,symbol,family,week_start)
);
CREATE INDEX IF NOT EXISTS sentinel_cloud_strategy_weekly_recent
 ON sentinel_cloud_strategy_weekly(account_id,week_start DESC,symbol);
