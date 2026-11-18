"""Read-only source-aware MT5 broker Depth-of-Market sampler.

Broker DOM (particularly CFD/FX) is not exchange-wide consolidated order flow.
No synthetic order levels, trading instructions, or inferred market fills.
"""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass
import math
import time

@dataclass(frozen=True)
class BookInsight:
    status: str
    source: str = "MT5_BROKER_DOM"
    imbalance: float | None = None
    microprice: float | None = None
    spread_bps: float | None = None
    samples: int = 0
    persistent_side: int = 0


class BookObserver:
    def __init__(self, mt5, *, clock=None, history_size=30):
        self.mt5=mt5
        self.clock=clock or time.monotonic
        self.subscribed=set()
        self.history={}
        self.history_size=history_size

    def close(self):
        for symbol in tuple(self.subscribed):
            try:self.mt5.market_book_release(symbol)
            except Exception:pass
        self.subscribed.clear()
        self.history.clear()

    def inspect(self, symbol: str) -> BookInsight:
        try:
            if symbol not in self.subscribed:
                if not callable(getattr(self.mt5, "market_book_add", None)) or not self.mt5.market_book_add(symbol):
                    return BookInsight("BROKER_DOM_NOT_OFFERED")
                self.subscribed.add(symbol)
            levels = self.mt5.market_book_get(symbol)
            if not levels:
                self.history.pop(symbol, None)
                return BookInsight("BROKER_DOM_EMPTY")
            bids, asks = [], []
            buy_type=getattr(self.mt5,"BOOK_TYPE_BUY",1)
            sell_type=getattr(self.mt5,"BOOK_TYPE_SELL",2)
            for p in levels:
                t=getattr(p,"type",None)
                # Market-type rows are not passive resting liquidity.
                if t not in (buy_type,sell_type):
                    continue
                price=getattr(p,"price",None)
                volume=getattr(p,"volume_dbl",None)
                if volume is None:volume=getattr(p,"volume_real",None)
                if volume is None:volume=getattr(p,"volume",None)
                if not (isinstance(price,(int,float)) and math.isfinite(price) and price>0 and
                        isinstance(volume,(int,float)) and math.isfinite(volume) and volume>0):
                    return BookInsight("BROKER_DOM_INVALID_LEVEL")
                (bids if t==buy_type else asks).append((float(price),float(volume)))
            if not bids or not asks:
                return BookInsight("BROKER_DOM_ONE_SIDE_MISSING")
            bids.sort(reverse=True)
            asks.sort()
            if bids[0][0]>=asks[0][0]:
                return BookInsight("BROKER_DOM_CROSSED")
            selected_b=bids[:5];selected_a=asks[:5]
            bv=sum(v for _,v in selected_b);av=sum(v for _,v in selected_a)
            im=(bv-av)/(bv+av)
            b,bvol=bids[0];a,avol=asks[0]
            micro=(a*bvol+b*avol)/(bvol+avol)
            spread=10000*(a-b)/((a+b)/2)
            now=self.clock()
            dq=self.history.setdefault(symbol,deque(maxlen=self.history_size))
            if dq and now<=dq[-1][0]:
                return BookInsight("BROKER_DOM_NON_MONOTONIC_TIME")
            dq.append((now,im))
            recent=[(t,v) for t,v in dq if now-t<=120]
            # 5 real snapshots over at least 20 seconds, consistent sign;
            # still observational, not a claim of fill or predictive edge.
            persist=0
            last_five=recent[-5:]
            if len(last_five)==5 and last_five[-1][0]-last_five[0][0]>=20:
                signs=[1 if v>=.15 else -1 if v<=-.15 else 0 for _,v in last_five]
                if all(x==signs[0] and x!=0 for x in signs):
                    persist=signs[0]
            return BookInsight("BROKER_DOM_OBSERVED",imbalance=round(im,5),
                microprice=micro,spread_bps=round(spread,4),samples=len(recent),
                persistent_side=persist)
        except Exception:
            return BookInsight("BROKER_DOM_READ_ERROR")
