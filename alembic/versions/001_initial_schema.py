"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # trades table
    op.create_table(
        "trades",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticket", sa.String(64), nullable=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("market_type", sa.String(10), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("trading_mode", sa.String(10), nullable=False, server_default="paper"),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("current_price", sa.Float(), nullable=True),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("lot_size", sa.Float(), nullable=False),
        sa.Column("stop_loss", sa.Float(), nullable=False),
        sa.Column("take_profit_1", sa.Float(), nullable=False),
        sa.Column("take_profit_2", sa.Float(), nullable=True),
        sa.Column("take_profit_3", sa.Float(), nullable=True),
        sa.Column("atr_at_entry", sa.Float(), nullable=True),
        sa.Column("risk_amount", sa.Float(), nullable=True),
        sa.Column("risk_reward_ratio", sa.Float(), nullable=True),
        sa.Column("pnl", sa.Float(), server_default="0"),
        sa.Column("pnl_pips", sa.Float(), server_default="0"),
        sa.Column("breakeven_moved", sa.Boolean(), server_default="false"),
        sa.Column("breakeven_price", sa.Float(), nullable=True),
        sa.Column("tp1_hit", sa.Boolean(), server_default="false"),
        sa.Column("tp2_hit", sa.Boolean(), server_default="false"),
        sa.Column("tp3_hit", sa.Boolean(), server_default="false"),
        sa.Column("session", sa.String(20), nullable=True),
        sa.Column("ai_confidence", sa.Float(), nullable=True),
        sa.Column("signal_id", sa.Integer(), nullable=True),
        sa.Column("strategy", sa.String(50), nullable=True),
        sa.Column("timeframe", sa.String(10), nullable=True),
        sa.Column("setup_notes", sa.Text(), nullable=True),
        sa.Column("meta_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trades_id", "trades", ["id"])
    op.create_index("ix_trades_symbol", "trades", ["symbol"])
    op.create_index("ix_trades_status", "trades", ["status"])
    op.create_index("ix_trades_ticket", "trades", ["ticket"], unique=True)
    op.create_index("ix_trades_signal_id", "trades", ["signal_id"])

    # signals table
    op.create_table(
        "signals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("market_type", sa.String(10), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("stop_loss", sa.Float(), nullable=False),
        sa.Column("take_profit_1", sa.Float(), nullable=False),
        sa.Column("take_profit_2", sa.Float(), nullable=True),
        sa.Column("take_profit_3", sa.Float(), nullable=True),
        sa.Column("atr", sa.Float(), nullable=True),
        sa.Column("h1_bias", sa.String(10), nullable=True),
        sa.Column("m15_trend", sa.String(10), nullable=True),
        sa.Column("m5_signal", sa.String(10), nullable=True),
        sa.Column("liquidity_sweep_detected", sa.Boolean(), server_default="false"),
        sa.Column("bos_detected", sa.Boolean(), server_default="false"),
        sa.Column("pullback_entry", sa.Boolean(), server_default="false"),
        sa.Column("ai_confidence", sa.Float(), nullable=True),
        sa.Column("ai_features", sa.JSON(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("session", sa.String(20), nullable=True),
        sa.Column("news_clear", sa.Boolean(), server_default="true"),
        sa.Column("risk_reward", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signals_id", "signals", ["id"])
    op.create_index("ix_signals_symbol", "signals", ["symbol"])
    op.create_index("ix_signals_status", "signals", ["status"])

    # performance_metrics table
    op.create_table(
        "performance_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("market_type", sa.String(10), nullable=False),
        sa.Column("total_trades", sa.Integer(), server_default="0"),
        sa.Column("winning_trades", sa.Integer(), server_default="0"),
        sa.Column("losing_trades", sa.Integer(), server_default="0"),
        sa.Column("win_rate", sa.Float(), server_default="0"),
        sa.Column("total_pnl", sa.Float(), server_default="0"),
        sa.Column("total_pnl_pips", sa.Float(), server_default="0"),
        sa.Column("avg_win", sa.Float(), server_default="0"),
        sa.Column("avg_loss", sa.Float(), server_default="0"),
        sa.Column("profit_factor", sa.Float(), server_default="0"),
        sa.Column("max_drawdown", sa.Float(), server_default="0"),
        sa.Column("max_consecutive_losses", sa.Integer(), server_default="0"),
        sa.Column("sharpe_ratio", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # session_stats table
    op.create_table(
        "session_stats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("session_name", sa.String(20), nullable=False),
        sa.Column("trades_taken", sa.Integer(), server_default="0"),
        sa.Column("trades_won", sa.Integer(), server_default="0"),
        sa.Column("pnl", sa.Float(), server_default="0"),
        sa.Column("signals_generated", sa.Integer(), server_default="0"),
        sa.Column("signals_executed", sa.Integer(), server_default="0"),
        sa.Column("signals_rejected", sa.Integer(), server_default="0"),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("session_stats")
    op.drop_table("performance_metrics")
    op.drop_table("signals")
    op.drop_table("trades")
