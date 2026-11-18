"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const book=require("../brain/orderbook.js");
const base=(timestamp,source="BINANCE_SPOT_DEPTH")=>({
 source,symbol:"BTCUSDT",timestamp,
 bids:[[9999,12],[9998,8],[9997,7]],
 asks:[[10000,4],[10001,5],[10002,5]]
});
test("L2 imbalance and microprice are descriptive, not executable orders",()=>{
 const now=Date.UTC(2026,10,18,15,0);
 const x=book.inspect(base(now),{now});
 assert.equal(x.status,"RESEARCH_ONLY");
 assert.ok(x.imbalance>0&&x.imbalance<1);
 assert.ok(x.microprice>9999&&x.microprice<10000);
 assert.equal(x.orders_enabled,false);
 assert.equal(x.execution_signal,null);
 assert.equal(x.caveat,"VENUE_SPECIFIC_SPOT_BOOK");
});
test("unknown, stale, crossed, zero-sized and untrusted source levels fail closed",()=>{
 const now=Date.UTC(2026,10,18,15,0);
 const invalid=[
  {...base(now),source:"UNTRUSTED"},
  base(now-5000),
  {...base(now),bids:[[10001,10]]},
  {...base(now),asks:[[10000,0]]},
  {...base(now),bids:[[9999,4],[9999,3]]},
  {...base(now),timestamp:now+1000}
 ];
 for(const s of invalid){
  const x=book.inspect(s,{now});
  assert.equal(x.status,"UNUSABLE");assert.equal(x.orders_enabled,false);
 }
});
test("persistence requires 20 fresh sequential same-venue snapshots over time",()=>{
 const now=Date.UTC(2026,10,18,15,0);
 const series=Array.from({length:20},(_,i)=>base(now-2400+i*120));
 assert.equal(book.studyPersistence(series.slice(1),{now}).status,"INSUFFICIENT_SNAPSHOTS");
 assert.equal(book.studyPersistence(series,{now}).status,"PERSISTENCE_OBSERVED_NOT_PROVEN");
 assert.equal(book.studyPersistence([...series.slice(0,19),base(now+5000)],{now}).status,"INVALID_SEQUENCE_OR_STALE");
 assert.equal(book.studyPersistence([...series.slice(0,19),base(now,"MT5_BROKER_DOM")],{now}).status,"INVALID_SEQUENCE_OR_STALE");
});
