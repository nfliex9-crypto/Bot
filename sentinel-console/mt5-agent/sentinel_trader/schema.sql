-- Apply only when deploying the paired demo telemetry bridge. No trading tables
-- or order APIs are created. Never use a public Neon read/write credential.
CREATE TABLE IF NOT EXISTS sentinel_independent_trader_status (
  agent_id uuid PRIMARY KEY REFERENCES sentinel_mt5_agents(agent_id) ON DELETE CASCADE,
  account_last4 text NOT NULL,
  snapshot jsonb NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT NOW()
);
