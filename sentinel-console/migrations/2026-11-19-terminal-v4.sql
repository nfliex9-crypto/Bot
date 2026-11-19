-- Sentinel V4: additive read-only dashboard indexes.
-- Supports account-scoped newest-first quotes, broker scans and research history.
-- No trading controls, strategy changes or destructive operations.
CREATE INDEX IF NOT EXISTS sentinel_quote_account_observed_desc
 ON sentinel_autonomy_spread_observations(account_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS sentinel_trader_cycle_account_observed_desc
 ON sentinel_cloud_trader_cycles(account_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS sentinel_research_cycle_account_started_desc
 ON sentinel_autonomy_cycles(account_id, started_at DESC);
