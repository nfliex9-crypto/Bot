"use strict";
const {test}=require("node:test"),assert=require("node:assert/strict");
const c=require("../worker/orderflow/composite-strategies.js");
const MS=300000,START=Date.UTC(2026,10,1);
function bar(i,{open=100,high=101,low=99,close=100,delta=0}={}){
 return {openTime:START+i*MS,closeTime:START+(i+1)*MS,barMs:MS,
  sessionId:"UTC-TEST",symbol:"BTCUSDT",venue:"TEST_EXCHANGE",
  sourceQuality:"VERIFIED_AGGRESSOR_TRADES",closed:true,
  open,high,low,close,delta,volume:Math.abs(delta)+100,
  buyVolume:(Math.abs(delta)+100+delta)/2,
  sellVolume:(Math.abs(delta)+100-delta)/2,
  maxIntrabarDelta:Math.max(0,delta),minIntrabarDelta:Math.min(0,delta)};
}
test("sweep of prior highs + negative divergence + closed bearish BOS emits SHORT",()=>{
 const xs=Array.from({length:32},(_,i)=>bar(i));
 xs[30]=bar(30,{open:100.5,high:102,low:99.5,close:100.7,delta:-8});
 xs[31]=bar(31,{open:100.4,high:100.8,low:98.7,close:99.0,delta:-6});
 const s=c.sweepDivergenceBos(xs,31);
 assert.ok(s);assert.equal(s.family,c.ID_SWEEP);assert.equal(s.side,"SHORT");
 assert.equal(s.detail.sweepTime,xs[30].openTime);assert.equal(s.executionEnabled,false);
});
test("sweep + divergence alone is not enough without BOS close",()=>{
 const xs=Array.from({length:32},(_,i)=>bar(i));
 xs[30]=bar(30,{open:100.5,high:102,low:99.5,close:100.7,delta:-8});
 xs[31]=bar(31,{open:100.5,high:100.8,low:99.8,close:100.0,delta:-6});
 assert.equal(c.sweepDivergenceBos(xs,31),null);
});
test("invalidated sweep cannot produce late signal",()=>{
 const xs=Array.from({length:34},(_,i)=>bar(i));
 xs[30]=bar(30,{open:100.5,high:102,low:99.5,close:100.7,delta:-8});
 xs[31]=bar(31,{open:101,high:103,low:100,close:101.2,delta:3});
 xs[32]=bar(32,{open:101,high:101.5,low:98.5,close:98.7,delta:-3});
 assert.equal(c.sweepDivergenceBos(xs,32),null);
});
test("long sweep / positive delta divergence / bullish BOS",()=>{
 const xs=Array.from({length:32},(_,i)=>bar(i));
 xs[30]=bar(30,{open:99.6,high:100.5,low:98,close:99.3,delta:9});
 xs[31]=bar(31,{open:100,high:102,low:99,close:101,delta:4});
 const s=c.sweepDivergenceBos(xs,31);
 assert.ok(s);assert.equal(s.side,"LONG");
});
test("hourly bias only uses completed consecutive hours",()=>{
 const xs=Array.from({length:864},(_,i)=>{
  const open=100+i*.008,close=open+.008;
  return bar(i,{open,high:close+.02,low:open-.02,close,delta:0});
 });
 const h=c.hourlyBars(xs);
 assert.equal(h.length,72);
 assert.equal(c.hourlyBias(h,xs.at(-1).closeTime),1);
 assert.equal(c.hourlyBias(h,xs[1].closeTime),0);
 const missing=[...h.slice(0,20),...h.slice(21)];
 assert.equal(c.hourlyBias(missing,xs.at(-1).closeTime),0);
});
test("trend + 4-candle delta surge + breakout produces directional hypothesis",()=>{
 const xs=Array.from({length:864},(_,i)=>{
  const open=100+i*.008,close=open+.008;
  return bar(i,{open,high:close+.02,low:open-.02,close,delta:0});
 });
 for(let j=0;j<4;j++)xs[860+j].delta=[-4,1,2,3][j];
 xs[863]={...xs[863],close:xs[863].close+.3,high:xs[863].close+.4};
 const h=c.hourlyBars(xs),s=c.trendDeltaSurge(xs,863,h);
 assert.ok(s);assert.equal(s.family,c.ID_TREND);assert.equal(s.side,"LONG");
 assert.equal(s.executionEnabled,false);
 assert.throws(()=>c.signalsAt(xs,863,h,c.PARAMS,xs[863].closeTime-1),/VERIFIED_CLOSED/);
});
test("no data or open bar can pass research guard",()=>{
 assert.throws(()=>c.signalsAt([],0,[]),/VERIFIED_CLOSED/);
 const x=bar(0);x.closed=false;
 assert.throws(()=>c.signalsAt([x],0,[]),/VERIFIED_CLOSED/);
});
