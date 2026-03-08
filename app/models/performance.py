from sqlalchemy import Column, Integer, String, Float, DateTime, Date, JSON
from sqlalchemy.sql import func
from app.database import Base


class PerformanceMetrics(Base):
    __tablename__ = "performance_metrics"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, index=True)
    market_type = Column(String(10), nullable=False)

    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)

    win_rate = Column(Float, default=0.0)
    total_pnl = Column(Float, default=0.0)
    total_pnl_pips = Column(Float, default=0.0)

    avg_win = Column(Float, default=0.0)
    avg_loss = Column(Float, default=0.0)
    profit_factor = Column(Float, default=0.0)

    max_drawdown = Column(Float, default=0.0)
    max_consecutive_losses = Column(Integer, default=0)

    sharpe_ratio = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class SessionStats(Base):
    __tablename__ = "session_stats"

    id = Column(Integer, primary_key=True, index=True)
    session_date = Column(Date, nullable=False, index=True)
    session_name = Column(String(20), nullable=False)  # london | new_york | overlap

    trades_taken = Column(Integer, default=0)
    trades_won = Column(Integer, default=0)
    pnl = Column(Float, default=0.0)
    signals_generated = Column(Integer, default=0)
    signals_executed = Column(Integer, default=0)
    signals_rejected = Column(Integer, default=0)

    details = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
