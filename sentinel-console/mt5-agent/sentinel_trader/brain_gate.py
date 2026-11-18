"""Fail-closed bridge from Sentinel research evidence to local DEMO execution.

No network calls, no Grok interface, no model self-authorization. A strategy
approval is an explicit, time-bounded local research artifact. Historical
simulation is NOT forward performance; a demo trial can be opted into locally
without pretending to have proven expectancy.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re

FAMILIES = frozenset(("trend_pullback", "donchian_breakout"))
TRIAL_FLAG = "YES_UNVERIFIED_SENTINEL_DEMO_TRIAL"
SOURCE = "SENTINEL_RESEARCH_APPROVAL_V1"
ID_RE = re.compile(r"^[a-f0-9]{64}$")

@dataclass(frozen=True)
class Verdict:
    allowed: bool
    status: str
    evidence: str = "UNVERIFIED_NO_BROKER_FILL_PROOF"
    candidate_id: str = ""


def parse_utc(text: object) -> datetime | None:
    if not isinstance(text, str):
        return None
    try:
        t = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t.astimezone(timezone.utc) if t.tzinfo else None


def approval(settings, signal, now: float) -> Verdict:
    """Validate *matching* approved research instead of trusting an AI label."""
    mode = getattr(settings, "strategy_policy", "verified_only")
    if mode == "demo_trial":
        if os.environ.get("SENTINEL_UNVERIFIED_DEMO_TRIAL") == TRIAL_FLAG:
            return Verdict(True, "LOCAL_UNVERIFIED_DEMO_TRIAL", "NOT_VALIDATED_EDGE")
        return Verdict(False, "DEMO_TRIAL_NOT_LOCALLY_AUTHORIZED")
    if mode != "verified_only":
        return Verdict(False, "INVALID_STRATEGY_POLICY")
    path = getattr(settings, "approval_path", "")
    if not path:
        return Verdict(False, "NO_APPROVED_SENTINEL_BRAIN_CANDIDATE")
    try:
        if Path(path).stat().st_size > 32768:
            return Verdict(False, "RESEARCH_APPROVAL_INVALID")
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return Verdict(False, "RESEARCH_APPROVAL_UNAVAILABLE")
    if not isinstance(doc, dict) or doc.get("source") != SOURCE or doc.get("version") != 1:
        return Verdict(False, "RESEARCH_APPROVAL_INVALID")
    if (doc.get("account_login") != settings.allowed_login or
        doc.get("account_server") != settings.allowed_server):
        return Verdict(False, "RESEARCH_APPROVAL_ACCOUNT_MISMATCH")
    made = parse_utc(doc.get("issued_at"))
    until = parse_utc(doc.get("expires_at"))
    current = datetime.fromtimestamp(now, timezone.utc)
    if (made is None or until is None or made > current or until < current or
        (until-made).total_seconds() > 30*86400 or (current-made).total_seconds() > 30*86400):
        return Verdict(False, "RESEARCH_APPROVAL_EXPIRED_OR_FUTURE")
    candidates = doc.get("candidates")
    if not isinstance(candidates, list) or len(candidates) > 100:
        return Verdict(False, "RESEARCH_APPROVAL_INVALID")
    matching = [x for x in candidates if isinstance(x, dict) and
                x.get("symbol") == signal.symbol and x.get("family") == signal.family and
                x.get("timeframe") == "M15"]
    if len(matching) != 1:
        return Verdict(False, "NO_APPROVED_SENTINEL_BRAIN_CANDIDATE")
    c = matching[0]
    if not (isinstance(c.get("candidate_id"), str) and ID_RE.fullmatch(c["candidate_id"]) and
            isinstance(c.get("dataset_id"), str) and ID_RE.fullmatch(c["dataset_id"]) and
            c.get("broker_costs_verified") is True and c.get("reviewed_by_operator") is True):
        return Verdict(False, "RESEARCH_EVIDENCE_INCOMPLETE")
    # All thresholds are independent requirements. The data source is recorded,
    # not presumed from strategy score or a dashboard 'approved' label.
    ints = {"validation_trades": 30, "holdout_trades": 20,
            "forward_trades": 20, "forward_days": 10}
    for key, minimum in ints.items():
        value = c.get(key)
        if type(value) is not int or value < minimum:
            return Verdict(False, "RESEARCH_EVIDENCE_INCOMPLETE")
    for key in ("validation_expectancy_r", "holdout_expectancy_r",
                "forward_expectancy_r", "double_cost_expectancy_r", "robust_lower_bound_r"):
        value = c.get(key)
        if type(value) not in (float,int) or not math.isfinite(value) or value <= 0:
            return Verdict(False, "RESEARCH_EVIDENCE_NOT_POSITIVE")
    return Verdict(True, "BRAIN_EVIDENCE_APPROVED_FOR_DEMO", "REVIEWED_DEMO_RESEARCH_ONLY", c["candidate_id"])
