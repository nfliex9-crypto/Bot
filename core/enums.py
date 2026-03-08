from enum import Enum


class Market(str, Enum):
    FOREX = "forex"
    CRYPTO = "crypto"


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"


class Bias(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class SignalType(str, Enum):
    LIQUIDITY_SWEEP = "liquidity_sweep"
    BREAK_OF_STRUCTURE = "break_of_structure"
    PULLBACK_ENTRY = "pullback_entry"


class TradeStatus(str, Enum):
    PENDING = "pending"
    OPEN = "open"
    PARTIAL_CLOSE = "partial_close"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


class SessionName(str, Enum):
    LONDON = "london"
    NEW_YORK = "new_york"
    OVERLAP = "overlap"
    CLOSED = "closed"


class Timeframe(str, Enum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"
