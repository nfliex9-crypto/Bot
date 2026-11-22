"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const intelligence=require("../worker/cloud-trader/regime-intelligence.js");
const risk=require("../worker/cloud-trader/adaptive-risk.js");
const start=Date.UTC(2026,10,23,9);
function fixture(){
 const m15=Array.from({length:120},(_,i)=>{
  const time=start+(i-120)*900000,open=100+i*.08,close=open+.2;
  return {time,open,close,high:close+.12,low:open-.11};
 });
 const h1=Array.from({length:100},(_,i)=>{
  const time=start+(i-100)*3600000,open=90+i*.16,close=open+.18;
  return {time,open,close,high:close+.1,low:open-.15};
 });
 const signal={symbol:"BTCUSD",family:"pdf_sweep_bos",side:1,
  bar_time:m15.at(-1).time,reference_close:m15.at(-1).close,
  atr:intelligence.atr14(m15),stop_atr:1.7,reward_r:2};
 return {m15,h1,signal,equity:5000,dayStartEquity:5000,baseRiskPct:.25};
}
test("V2 detects aligned trend from completed M15/H1 OHLC",()=>{
 const m=intelligence.analyze(fixture().m15,fixture().h1);
 assert.equal(m.ok,true);assert.equal(m.regime,"TRENDING");
 assert.equal(m.h1Direction,1);assert.equal(m.aligned,true);
 assert.equal(m.executionVerified,false);
});
test("V2 detects ranging market from oscillating low-efficiency closed bars",()=>{
 const f=fixture();
 f.m15=f.m15.map((b,i)=>{const v=100+Math.sin(i*Math.PI/2)*.12;
  return {...b,open:v-.01,close:v+.01,high:v+.2,low:v-.2}});
 f.h1=f.h1.map((b,i)=>{const v=100+Math.sin(i*Math.PI/2)*.10;
  return {...b,open:v-.01,close:v+.01,high:v+.2,low:v-.2}});
 const m=intelligence.analyze(f.m15,f.h1);
 assert.equal(m.ok,true);assert.equal(m.regime,"RANGING",JSON.stringify(m));
});
test("V2 recognizes a volatility shock without inventing order-flow data",()=>{
 const f=fixture(),last=f.m15.at(-1);
 f.m15[f.m15.length-1]={...last,high:last.high+12,low:last.low-8};
 const m=intelligence.analyze(f.m15,f.h1);
 assert.equal(m.ok,true);assert.equal(m.regime,"VOLATILE");
 assert.equal(m.riskFactor,.25);
 assert.match(m.evidence,/CLOSED_OHLC/);
});
test("V2 rejects malformed, out-of-order or insufficient bars",()=>{
 const f=fixture();
 assert.equal(intelligence.analyze(f.m15.slice(0,30),f.h1).ok,false);
 assert.equal(intelligence.analyze([...f.m15,{...f.m15.at(-1)}],f.h1).ok,false);
 assert.equal(intelligence.analyze(f.m15.map((b,i)=>i===7?{...b,low:b.high+1}:b),f.h1).ok,false);
});
test("V2 uses signal candle only and rejects future H1 leakage",()=>{
 const f=fixture();
 assert.equal(risk.evaluate({...f,signal:{...f.signal,bar_time:f.signal.bar_time-900000}}).allowed,false);
 const h1=f.h1.map((b,i)=>i===99?{...b,time:f.m15.at(-1).time+3600000}:b);
 assert.equal(risk.evaluate({...f,h1}).reason,"ADAPTIVE_SIGNAL_BAR_MISMATCH");
});
test("V2 adapts to strong signal without a fixed per-trade 0.25% size",()=>{
 const x=risk.evaluate(fixture());
 assert.equal(x.allowed,true,JSON.stringify(x));
 assert.ok(x.riskPct>.25);assert.ok(x.score>.5);
 assert.equal(x.market.regime,"TRENDING");
 assert.equal(x.executionEnabled,false);
});
test("V2 de-risks with exposure rather than arbitrary total-position count",()=>{
 const f=fixture(),a=risk.evaluate(f);
 const b=risk.evaluate({...f,positions:Array.from({length:12},(_,i)=>({symbol:"SYM"+i}))});
 assert.equal(b.allowed,true);assert.ok(b.riskPct<a.riskPct);assert.equal(b.openExposureCount,12);
});
test("V2 de-risks on account drawdown without fixed 1% daily-loss veto",()=>{
 const f=fixture();
 const a=risk.evaluate({...f,equity:4950});
 const b=risk.evaluate({...f,equity:4000});
 assert.equal(a.allowed,true);assert.equal(b.allowed,true);
 assert.ok(b.riskPct<a.riskPct);
});
test("V2 blocks HTF trend conflict and unknown source family",()=>{
 const f=fixture();
 assert.equal(risk.evaluate({...f,signal:{...f.signal,side:-1}}).reason,"H1_TREND_AGAINST_SIGNAL");
 assert.equal(risk.evaluate({...f,signal:{...f.signal,family:"unknown"}}).reason,"UNKNOWN_STRATEGY_FAMILY");
});
test("V2 gross-only decisions are invariant to fake fee/spread columns",()=>{
 const f=fixture(),a=risk.evaluate(f);
 const b=risk.evaluate({...f,m15:f.m15.map(x=>({...x,spread:5000,commission:800,swap:1000})),
  h1:f.h1.map(x=>({...x,spread:5000,slippage:1000}))});
 assert.deepEqual(a,b);
});
test("V2 rejects unknown positions and absent start equity",()=>{
 const f=fixture();
 assert.equal(risk.evaluate({...f,positions:[{}]}).reason,"PORTFOLIO_EXPOSURE_UNVERIFIED");
 assert.equal(risk.evaluate({...f,dayStartEquity:null}).reason,"ADAPTIVE_RISK_DATA_INCOMPLETE");
});
