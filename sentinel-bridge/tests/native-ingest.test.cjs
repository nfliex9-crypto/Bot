"use strict";
const test=require("node:test"),assert=require("node:assert/strict");
const {normalizeUpload}=require("../native-ingest.js");
const now=Date.UTC(2026,10,18,15,0,0);
const example=(t=Math.floor((now-3600000)/1000))=>({
 source:"LOCAL_MT5_DEMO_TERMINAL",trade_mode:"demo",symbol:"XAUUSD",timeframe:"M15",
 candles:[{timestamp:t,open:4000,high:4003,low:3999,close:4002,spread:.2,tickVolume:200}]
});
test("native MT5 demo data are always tagged unverified and non-executable",()=>{
 const x=normalizeUpload(example(),{now});
 assert.equal(x.bars.length,1);
 assert.equal(x.bars[0].spread,.2);
 assert.equal(x.orders_enabled,false);
 assert.equal(x.unverified,true);
});
test("reject live account, forged source, malformed prices and an open bar",()=>{
 for(const [field,value] of [["trade_mode","real"],["source","MOCK"],
  ["candles",[{timestamp:Math.floor(now/1000),open:1,high:2,low:.5,close:1,spread:.1,tickVolume:1}]],
  ["candles",[{timestamp:Math.floor((now-3600000)/1000),open:4,high:3,low:2,close:2.5,spread:0,tickVolume:1}]]]){
  const s={...example(),[field]:value};
  assert.throws(()=>normalizeUpload(s,{now}));
 }
});
test("deduplicates timestamps by rejecting and never fills missing spreads with zero",()=>{
 const x=example(),row=x.candles[0];
 x.candles=[{...row,spread:0},{...row,spread:null}];
 assert.throws(()=>normalizeUpload(x,{now}),/DUPLICATE_BAR/);
 x.candles=[{...row,spread:0}];
 const out=normalizeUpload(x,{now});
 assert.equal(out.bars[0].spread,null);
});
