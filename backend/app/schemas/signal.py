from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from app.models.signal import SignalStatus


class SignalCreate(BaseModel):
    symbol: str
    market: str
    timeframe: str
    direction: str
    entry_zone_low: Optional[float] = None
    entry_zone_high: Optional[float] = None
    stop_loss: Optional[float] = None
    tp1: Optional[float] = None
    tp2: Optional[float] = None
    tp3: Optional[float] = None
    liquidity_sweep_detected: bool = False
    bos_detected: bool = False
    pullback_confirmed: bool = False
    sweep_level: Optional[float] = None
    bos_level: Optional[float] = None
    atr_value: Optional[float] = None
    confidence_score: Optional[float] = None
    feature_importance: Optional[Dict[str, Any]] = None
    model_version: Optional[str] = None
    market_structure: Optional[str] = None
    session: Optional[str] = None
    notes: Optional[str] = None


class SignalRead(BaseModel):
    id: int
    symbol: str
    market: str
    timeframe: str
    direction: str
    status: SignalStatus
    entry_zone_low: Optional[float]
    entry_zone_high: Optional[float]
    stop_loss: Optional[float]
    tp1: Optional[float]
    tp2: Optional[float]
    tp3: Optional[float]
    liquidity_sweep_detected: bool
    bos_detected: bool
    pullback_confirmed: bool
    sweep_level: Optional[float]
    bos_level: Optional[float]
    atr_value: Optional[float]
    confidence_score: Optional[float]
    feature_importance: Optional[Dict[str, Any]]
    model_version: Optional[str]
    market_structure: Optional[str]
    session: Optional[str]
    notes: Optional[str]
    created_at: datetime
    expires_at: Optional[datetime]
    executed_at: Optional[datetime]

    model_config = {"from_attributes": True, "protected_namespaces": ()}
