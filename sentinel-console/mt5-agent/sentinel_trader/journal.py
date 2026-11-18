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
          CREATE TABLE IF NOT EXISTS research_decision (
            id TEXT PRIMARY KEY, account INTEGER NOT NULL, symbol TEXT NOT NULL,
            family TEXT NOT NULL, side INTEGER NOT NULL, bar_time INTEGER NOT NULL,
            brain_status TEXT NOT NULL, book_status TEXT NOT NULL,
            status TEXT NOT NULL, first_seen INTEGER NOT NULL, last_seen INTEGER NOT NULL,
            reviewed_as_execution INTEGER NOT NULL DEFAULT 0
          );
          CREATE INDEX IF NOT EXISTS idx_research_decision_account
          ON research_decision(account,bar_time);
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

    def record_decision(self, oid: str, account: int, symbol: str, family: str,
                        side: int, bar_time: int, brain_status: str,
                        book_status: str, status: str):
        # A signal is NOT a broker order or deal. No P&L is inferred here.
        if not oid or not symbol or not family or not status or side not in (-1,1):
            raise ValueError("INVALID_RESEARCH_DECISION")
        now=int(time.time())
        with self.db:
            self.db.execute("""INSERT INTO research_decision
            (id,account,symbol,family,side,bar_time,brain_status,book_status,status,first_seen,last_seen)
            VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
            brain_status=excluded.brain_status,book_status=excluded.book_status,
            status=excluded.status,last_seen=excluded.last_seen""",
            (oid,account,symbol,family,side,bar_time,brain_status[:90],book_status[:90],
             status[:90],now,now))

    def recent_decisions(self, account: int, limit: int=30) -> list[dict]:
        rows=self.db.execute("""SELECT symbol,family,side,bar_time,brain_status,book_status,
                             status,first_seen,last_seen FROM research_decision
                             WHERE account=? ORDER BY last_seen DESC LIMIT ?""",
                             (account,max(1,min(limit,100)))).fetchall()
        return [dict(zip(("symbol","family","side","bar_time","brain_status",
                          "book_status","status","first_seen","last_seen"),r)) for r in rows]

    def all_intents(self):
        return self.db.execute("SELECT id,symbol,family,bar_time,status,note FROM intent ORDER BY created_at DESC").fetchall()
