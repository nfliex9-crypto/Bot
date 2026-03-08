"""
Database repository: CRUD operations for trades, signals, and account snapshots.
Uses async SQLAlchemy for non-blocking DB access.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import create_engine, select, desc
from sqlalchemy.orm import Session, sessionmaker

from config.settings import DatabaseConfig
from core.logger import get_logger
from core.models import AccountState, Trade, TradeSignal
from database.models import (
    AccountSnapshot, Base, MLTrainingData, SignalRecord, TradeRecord,
)

logger = get_logger("database")


class TradingRepository:
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.engine = None
        self.SessionLocal = None

    def connect(self):
        try:
            self.engine = create_engine(self.config.sync_url, pool_pre_ping=True, pool_size=5)
            Base.metadata.create_all(self.engine)
            self.SessionLocal = sessionmaker(bind=self.engine)
            logger.info("Database connected and tables created")
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            logger.info("Running without database persistence")
            self.engine = None

    def _get_session(self) -> Optional[Session]:
        if self.SessionLocal is None:
            return None
        return self.SessionLocal()

    def save_signal(self, signal: TradeSignal):
        session = self._get_session()
        if not session:
            return
        try:
            record = SignalRecord(
                signal_id=signal.signal_id,
                symbol=signal.symbol,
                direction=signal.direction.value,
                entry_price=signal.entry_price,
                stop_loss=signal.stop_loss,
                tp1=signal.tp1, tp2=signal.tp2, tp3=signal.tp3,
                confidence=signal.confidence,
                ai_score=signal.ai_score,
                strength=signal.strength.value,
                market_bias=signal.market_bias.value,
                reason=signal.reason,
                timestamp=signal.timestamp,
            )
            session.add(record)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving signal: {e}")
        finally:
            session.close()

    def save_trade(self, trade: Trade):
        session = self._get_session()
        if not session:
            return
        try:
            record = TradeRecord(
                trade_id=trade.trade_id,
                signal_id=trade.signal.signal_id if trade.signal else None,
                symbol=trade.symbol,
                market=trade.market,
                direction=trade.direction.value,
                entry_price=trade.entry_price,
                stop_loss=trade.stop_loss,
                tp1=trade.tp1, tp2=trade.tp2, tp3=trade.tp3,
                position_size=trade.position_size,
                status=trade.status.value,
                pnl=trade.pnl,
                confidence=trade.signal.confidence if trade.signal else 0,
                ai_score=trade.signal.ai_score if trade.signal else 0,
                risk_reward=trade.signal.risk_reward if trade.signal else 0,
                reason=trade.signal.reason if trade.signal else "",
                market_bias=trade.signal.market_bias.value if trade.signal else "",
                opened_at=trade.opened_at,
                broker_order_id=trade.broker_order_id,
                metadata_json=json.dumps(trade.signal.metadata) if trade.signal else "{}",
            )
            session.add(record)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving trade: {e}")
        finally:
            session.close()

    def update_trade(self, trade: Trade):
        session = self._get_session()
        if not session:
            return
        try:
            record = session.query(TradeRecord).filter_by(trade_id=trade.trade_id).first()
            if record:
                record.status = trade.status.value
                record.pnl = trade.pnl
                record.pnl_pct = trade.pnl_pct
                record.closed_at = trade.closed_at
                record.tp1_hit = trade.tp1_hit
                record.tp2_hit = trade.tp2_hit
                record.tp3_hit = trade.tp3_hit
                record.breakeven_set = trade.breakeven_set
                record.stop_loss = trade.stop_loss
                session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating trade: {e}")
        finally:
            session.close()

    def save_account_snapshot(self, account: AccountState):
        session = self._get_session()
        if not session:
            return
        try:
            snapshot = AccountSnapshot(
                balance=account.balance,
                equity=account.equity,
                drawdown=account.current_drawdown,
                open_trades=account.open_trades,
                daily_pnl=account.daily_pnl,
                total_trades=account.total_trades,
                win_rate=account.win_rate,
            )
            session.add(snapshot)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving snapshot: {e}")
        finally:
            session.close()

    def save_ml_data(self, trade_id: str, features: dict, label: int):
        session = self._get_session()
        if not session:
            return
        try:
            record = MLTrainingData(
                trade_id=trade_id,
                features_json=json.dumps(features),
                label=label,
            )
            session.add(record)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving ML data: {e}")
        finally:
            session.close()

    def get_ml_training_data(self) -> tuple:
        """Load all ML training data for model retraining."""
        import numpy as np
        import pandas as pd

        session = self._get_session()
        if not session:
            return pd.DataFrame(), np.array([])

        try:
            records = session.query(MLTrainingData).all()
            if not records:
                return pd.DataFrame(), np.array([])

            features_list = []
            labels = []
            for r in records:
                features_list.append(json.loads(r.features_json))
                labels.append(r.label)

            return pd.DataFrame(features_list), np.array(labels)
        except Exception as e:
            logger.error(f"Error loading ML data: {e}")
            return pd.DataFrame(), np.array([])
        finally:
            session.close()

    def get_recent_trades(self, limit: int = 50) -> list[dict]:
        session = self._get_session()
        if not session:
            return []
        try:
            records = (
                session.query(TradeRecord)
                .order_by(desc(TradeRecord.opened_at))
                .limit(limit)
                .all()
            )
            return [
                {
                    "trade_id": r.trade_id,
                    "symbol": r.symbol,
                    "direction": r.direction,
                    "entry_price": r.entry_price,
                    "stop_loss": r.stop_loss,
                    "pnl": r.pnl,
                    "status": r.status,
                    "confidence": r.confidence,
                    "opened_at": r.opened_at.isoformat() if r.opened_at else None,
                    "closed_at": r.closed_at.isoformat() if r.closed_at else None,
                }
                for r in records
            ]
        except Exception as e:
            logger.error(f"Error loading trades: {e}")
            return []
        finally:
            session.close()

    def get_account_history(self, days: int = 30) -> list[dict]:
        session = self._get_session()
        if not session:
            return []
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            records = (
                session.query(AccountSnapshot)
                .filter(AccountSnapshot.timestamp >= cutoff)
                .order_by(AccountSnapshot.timestamp)
                .all()
            )
            return [
                {
                    "timestamp": r.timestamp.isoformat(),
                    "balance": r.balance,
                    "equity": r.equity,
                    "drawdown": r.drawdown,
                    "win_rate": r.win_rate,
                }
                for r in records
            ]
        except Exception as e:
            logger.error(f"Error loading history: {e}")
            return []
        finally:
            session.close()
