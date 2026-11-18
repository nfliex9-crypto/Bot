from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0,str(next(p for p in Path(__file__).resolve().parents if (p/"sentinel_trader").is_dir())))
from types import SimpleNamespace as S
import unittest
from sentinel_trader.orderflow import BookObserver

class Provider:
    BOOK_TYPE_BUY=1
    BOOK_TYPE_SELL=2
    BOOK_TYPE_BUY_MARKET=3
    def __init__(self):
        self.added=[];self.released=[]
        self.entries=[S(type=1,price=99,volume_dbl=10),S(type=2,price=100,volume_dbl=2),
                      S(type=3,price=99.5,volume_dbl=100000)]
    def market_book_add(self,s):self.added.append(s);return True
    def market_book_get(self,s):return self.entries
    def market_book_release(self,s):self.released.append(s);return True

class OrderflowTests(unittest.TestCase):
    def test_broker_book_observational_only(self):
        provider=Provider();clock=[0.0]
        book=BookObserver(provider,clock=lambda:clock[0])
        for i in range(5):
            clock[0]=i*6.0
            x=book.inspect("EURUSD")
        self.assertEqual(x.status,"BROKER_DOM_OBSERVED")
        self.assertGreater(x.imbalance,.6)
        self.assertEqual(x.persistent_side,1)
        self.assertEqual(len(provider.added),1)
        book.close();self.assertEqual(provider.released,["EURUSD"])
    def test_missing_depth_does_not_fake_liquidity(self):
        p=Provider();p.market_book_add=lambda s:False
        self.assertEqual(BookObserver(p).inspect("XAUUSD").status,"BROKER_DOM_NOT_OFFERED")
        p=Provider();p.entries=[]
        self.assertEqual(BookObserver(p).inspect("XAUUSD").status,"BROKER_DOM_EMPTY")
    def test_negative_canceled_or_crossed_levels_fail_closed(self):
        p=Provider()
        p.entries=[S(type=1,price=101,volume_dbl=1),S(type=2,price=100,volume_dbl=1)]
        self.assertEqual(BookObserver(p).inspect("XAUUSD").status,"BROKER_DOM_CROSSED")
        p.entries=[S(type=1,price=99,volume_dbl=-1),S(type=2,price=100,volume_dbl=1)]
        self.assertEqual(BookObserver(p).inspect("XAUUSD").status,"BROKER_DOM_INVALID_LEVEL")
    def test_last_five_must_span_20_seconds_not_earlier_samples(self):
        p=Provider();clock=[0.0];book=BookObserver(p,clock=lambda:clock[0])
        for t in [0,10,20,30,40,41,42,43,44]:
            clock[0]=t
            r=book.inspect("XAUUSD")
        self.assertEqual(r.status,"BROKER_DOM_OBSERVED")
        self.assertEqual(r.persistent_side,0)
        p.entries=[]
        self.assertEqual(book.inspect("XAUUSD").status,"BROKER_DOM_EMPTY")
        self.assertEqual(book.history.get("XAUUSD"),None)
    def test_read_order_book_never_sends_any_order(self):
        p=Provider();p.order_send=lambda r:self.fail("Must not create orders")
        book=BookObserver(p)
        self.assertEqual(book.inspect("BTCUSD").status,"BROKER_DOM_OBSERVED")
        self.assertEqual(book.inspect("BTCUSD").persistent_side,0)

if __name__=="__main__":unittest.main()
