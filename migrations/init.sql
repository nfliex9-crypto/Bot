-- Trading Bot Database Schema

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- ── Enums ─────────────────────────────────────────────────────────────────────

CREATE TYPE trade_status AS ENUM (
    'pending', 'open', 'partial_close', 'closed', 'cancelled', 'rejected'
);

CREATE TYPE trade_direction AS ENUM ('long', 'short');
CREATE TYPE market_type AS ENUM ('forex', 'crypto');
CREATE TYPE trading_mode AS ENUM ('paper', 'live');
CREATE TYPE signal_status AS ENUM ('pending', 'executed', 'rejected', 'expired');
CREATE TYPE close_reason AS ENUM (
    'tp1', 'tp2', 'tp3', 'stop_loss', 'break_even',
    'manual', 'max_drawdown', 'session_end', 'news_filter'
);

-- ── Trades Table ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS trades (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol          VARCHAR(20) NOT NULL,
    market          market_type NOT NULL,
    direction       trade_direction NOT NULL,
    status          trade_status NOT NULL DEFAULT 'pending',
    mode            trading_mode NOT NULL DEFAULT 'paper',

    entry_price     DECIMAL(18, 8),
    stop_loss       DECIMAL(18, 8) NOT NULL,
    tp1             DECIMAL(18, 8) NOT NULL,
    tp2             DECIMAL(18, 8) NOT NULL,
    tp3             DECIMAL(18, 8) NOT NULL,
    break_even_price DECIMAL(18, 8),

    lot_size        DECIMAL(10, 4) NOT NULL,
    risk_amount     DECIMAL(18, 2) NOT NULL,
    account_balance_at_open DECIMAL(18, 2),

    ai_confidence   DECIMAL(5, 4),
    signal_id       UUID,

    broker_ticket   VARCHAR(50),

    open_time       TIMESTAMPTZ,
    close_time      TIMESTAMPTZ,
    close_reason    close_reason,

    realized_pnl    DECIMAL(18, 2) DEFAULT 0,
    max_favorable_excursion DECIMAL(18, 8),
    max_adverse_excursion   DECIMAL(18, 8),

    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_trades_symbol ON trades(symbol);
CREATE INDEX idx_trades_status ON trades(status);
CREATE INDEX idx_trades_open_time ON trades(open_time DESC);
CREATE INDEX idx_trades_created_at ON trades(created_at DESC);
CREATE INDEX idx_trades_market ON trades(market);

-- ── Signals Table ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS signals (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol          VARCHAR(20) NOT NULL,
    market          market_type NOT NULL,
    direction       trade_direction NOT NULL,
    status          signal_status NOT NULL DEFAULT 'pending',

    htf_bias        VARCHAR(10),
    mtf_trend       VARCHAR(10),
    ltf_entry       VARCHAR(10),

    liquidity_swept BOOLEAN DEFAULT FALSE,
    bos_confirmed   BOOLEAN DEFAULT FALSE,
    pullback_valid  BOOLEAN DEFAULT FALSE,

    entry_price     DECIMAL(18, 8),
    stop_loss       DECIMAL(18, 8),
    tp1             DECIMAL(18, 8),
    tp2             DECIMAL(18, 8),
    tp3             DECIMAL(18, 8),
    atr_value       DECIMAL(18, 8),

    ai_confidence   DECIMAL(5, 4),
    ai_features     JSONB DEFAULT '{}',

    session         VARCHAR(20),
    news_clear      BOOLEAN DEFAULT TRUE,

    generated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ,
    executed_at     TIMESTAMPTZ,

    metadata        JSONB DEFAULT '{}'
);

CREATE INDEX idx_signals_symbol ON signals(symbol);
CREATE INDEX idx_signals_status ON signals(status);
CREATE INDEX idx_signals_generated_at ON signals(generated_at DESC);

-- ── Market Data Cache ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS market_data (
    id              BIGSERIAL PRIMARY KEY,
    symbol          VARCHAR(20) NOT NULL,
    market          market_type NOT NULL,
    timeframe       VARCHAR(10) NOT NULL,
    open_time       TIMESTAMPTZ NOT NULL,
    open            DECIMAL(18, 8) NOT NULL,
    high            DECIMAL(18, 8) NOT NULL,
    low             DECIMAL(18, 8) NOT NULL,
    close           DECIMAL(18, 8) NOT NULL,
    volume          DECIMAL(24, 8) NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(symbol, timeframe, open_time)
);

CREATE INDEX idx_market_data_symbol_tf ON market_data(symbol, timeframe);
CREATE INDEX idx_market_data_open_time ON market_data(open_time DESC);

-- ── Performance Metrics ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS performance_snapshots (
    id              BIGSERIAL PRIMARY KEY,
    snapshot_time   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    mode            trading_mode NOT NULL,
    balance         DECIMAL(18, 2) NOT NULL,
    equity          DECIMAL(18, 2) NOT NULL,
    open_trades     INT NOT NULL DEFAULT 0,
    total_trades    INT NOT NULL DEFAULT 0,
    winning_trades  INT NOT NULL DEFAULT 0,
    losing_trades   INT NOT NULL DEFAULT 0,
    total_pnl       DECIMAL(18, 2) NOT NULL DEFAULT 0,
    max_drawdown    DECIMAL(18, 2) NOT NULL DEFAULT 0,
    win_rate        DECIMAL(5, 4),
    profit_factor   DECIMAL(10, 4),
    sharpe_ratio    DECIMAL(10, 4),
    metadata        JSONB DEFAULT '{}'
);

CREATE INDEX idx_perf_snapshot_time ON performance_snapshots(snapshot_time DESC);

-- ── News Events ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS news_events (
    id              BIGSERIAL PRIMARY KEY,
    title           TEXT NOT NULL,
    currency        VARCHAR(10),
    impact          VARCHAR(10) NOT NULL,
    event_time      TIMESTAMPTZ NOT NULL,
    actual          VARCHAR(50),
    forecast        VARCHAR(50),
    previous        VARCHAR(50),
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_news_event_time ON news_events(event_time);
CREATE INDEX idx_news_currency ON news_events(currency);

-- ── Bot Sessions ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS bot_sessions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    start_time      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    end_time        TIMESTAMPTZ,
    mode            trading_mode NOT NULL,
    trades_taken    INT NOT NULL DEFAULT 0,
    session_pnl     DECIMAL(18, 2) NOT NULL DEFAULT 0,
    status          VARCHAR(20) NOT NULL DEFAULT 'active',
    metadata        JSONB DEFAULT '{}'
);

-- ── Updated At Trigger ────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_trades_updated_at
    BEFORE UPDATE ON trades
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
