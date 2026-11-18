"""The identity and trading switches are explicit; no credential storage."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json
import math


@dataclass(frozen=True)
class Settings:
    mode: str
    allowed_login: int
    allowed_server: str
    blocked_logins: tuple[int, ...]
    symbols: tuple[str, ...]
    magic: int
    risk_per_trade_pct: float
    max_daily_drawdown_pct: float
    max_positions: int
    max_lots: float
    max_spread_bps: float
    max_tick_age_seconds: int
    deviation_points: int
    poll_seconds: int
    journal_path: str
    status_path: str

    @classmethod
    def from_file(cls, path: str | Path) -> "Settings":
        cfg = json.loads(Path(path).read_text(encoding="utf-8"))
        result=cls(mode=str(cfg["mode"]), allowed_login=int(cfg["allowed_login"]),
            allowed_server=str(cfg["allowed_server"]),
            blocked_logins=tuple(int(x) for x in cfg.get("blocked_logins", [])),
            symbols=tuple(str(x) for x in cfg["symbols"]), magic=int(cfg["magic"]),
            risk_per_trade_pct=float(cfg["risk_per_trade_pct"]),
            max_daily_drawdown_pct=float(cfg["max_daily_drawdown_pct"]),
            max_positions=int(cfg["max_positions"]), max_lots=float(cfg["max_lots"]),
            max_spread_bps=float(cfg["max_spread_bps"]),
            max_tick_age_seconds=int(cfg["max_tick_age_seconds"]),
            deviation_points=int(cfg["deviation_points"]),
            poll_seconds=int(cfg["poll_seconds"]), journal_path=str(cfg["journal_path"]),
            status_path=str(cfg["status_path"]))
        result.validate()
        return result

    def validate(self):
        if self.mode not in ("research","demo_execution") or not (100000 <= self.magic <= 2_147_483_647):
            raise ValueError("INVALID_MODE_OR_MAGIC")
        if self.allowed_login <= 0 or self.allowed_login == 563722 or self.allowed_login in self.blocked_logins or not self.allowed_server:
            raise ValueError("EXCLUSIVE_SEPARATE_DEMO_ACCOUNT_REQUIRED")
        if len(self.symbols) < 1 or len(self.symbols)>8 or len(set(self.symbols))!=len(self.symbols) or any(
            not (2<=len(s)<=24 and all(c.isalnum() or c in "._#-" for c in s)) for s in self.symbols):
            raise ValueError("INVALID_SYMBOLS")
        if not (0 < self.risk_per_trade_pct <= 0.5 and 0 < self.max_daily_drawdown_pct <= 2.0):
            raise ValueError("INVALID_RISK_LIMITS")
        if not (1<=self.max_positions<=3 and 0<self.max_lots<=1.0 and 0<self.max_spread_bps<=30):
            raise ValueError("INVALID_PORTFOLIO_LIMITS")
        if not (3<=self.max_tick_age_seconds<=60 and 1<=self.deviation_points<=100 and 5<=self.poll_seconds<=300):
            raise ValueError("INVALID_RUNTIME_LIMITS")
        if not self.journal_path or not self.status_path:
            raise ValueError("STATUS_AND_JOURNAL_REQUIRED")
