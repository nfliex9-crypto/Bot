"""Crash-durable idempotency and daily equity guard state.

The intent is written before order_send. Unknown outcomes never auto-retry.
"""
from __future__ import annotations
import json
import sqlite3
import time
from pathlib import Path


class Journal:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path), isolation_level=None, timeout=15)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=15000")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS intent (
            id TEXT PRIMARY KEY, account INTEGER NOT NULL, symbol TEXT NOT NULL,
            family TEXT NOT NULL, bar_time INTEGER NOT NULL, side INTEGER NOT NULL,
            status TEXT NOT NULL, created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL, broker_order TEXT, note TEXT NOT NULL DEFAULT ''
          );
          CREATE TABLE IF NOT EXISTS baseline (
            account INTEGER NOT NULL, utc_day TEXT NOT NULL,
            start_equity REAL NOT NULL CHECK (start_equity > 0),
            PRIMARY KEY(account,utc_day)
          );
          CREATE INDEX IF NOT EXISTS idx_intent_account_symbol ON intent(account,symbol,status);
        """)

    def close(self):
        self.db.close()

    def reserve(self, id: str, account: int, symbol: str, family: str, bar_time: int, side: int) -> bool:
        now = int(time.time())
        with self.db:
            cursor = self.db.execute("INSERT OR IGNORE INTO intent(id,account,symbol,family,bar_time,side,status,created_at,updated_at) VALUES(?,?,?,?,?,?,'PREPARED',?,?)",
                                     (id,account,symbol,family,bar_time,side,now,now))
            return cursor.rowcount == 1

    def mark(self, id: str, status: str, note: str = "", broker_order: str = ""):
        if status not in ("PREFLIGHT_REJECTED", "NOT_SENT", "SUBMITTING", "UNKNOWN", "ACKNOWLEDGED", "CONFIRMED", "REJECTED"):
            raise ValueError("INVALID_JOURNAL_STATUS")
        with self.db:
            self.db.execute("UPDATE intent SET status=?,updated_at=?,note=?,broker_order=? WHERE id=?",
                            (status,int(time.time()),note[:240],broker_order[:40],id))

    def unresolved(self, account: int, symbol: str) -> list[tuple]:
        return self.db.execute("SELECT id,status FROM intent WHERE account=? AND symbol=? AND status IN ('PREPARED','SUBMITTING','UNKNOWN','ACKNOWLEDGED') ORDER BY created_at",
                               (account,symbol)).fetchall()

    def today_start_equity(self, account: int, utc_day: str, equity: float) -> float:
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO baseline(account,utc_day,start_equity) VALUES(?,?,?)",(account,utc_day,equity))
            row=self.db.execute("SELECT start_equity FROM baseline WHERE account=? AND utc_day=?",(account,utc_day)).fetchone()
        return float(row[0])

    def all_intents(self):
        return self.db.execute("SELECT id,symbol,family,bar_time,status,note FROM intent ORDER BY created_at DESC").fetchall()
