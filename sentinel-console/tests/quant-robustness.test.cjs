"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const {blockBootstrap,dayId}=require("../brain/robustness.js");
const {fingerprint}=require("../brain/provenance.js");
const engine=require("../brain/engine.js");
const iso=i=>new Date(Date.UTC(2026,4,1+i,9)).toISOString();
const dayTrades=(days,reward,countPerDay=1)=>Array.from({length:days*countPerDay},(_,i)=>({
 time:iso(Math.floor(i/countPerDay)),entryTime:iso(Math.floor(i/countPerDay)),rr:reward
}));
test("day-block resampling recognises correlated intraday trades as ONE day",()=>{
 const oneDay=dayTrades(1,1,200);
 const res=blockBootstrap(oneDay,{strategyId:"trend"});
 assert.equal(res.sample_trades,200);
 assert.equal(res.sample_days,1);
 assert.equal(res.eligible_for_paper_research,false);
 assert.equal(res.status,"INSUFFICIENT_INDEPENDENT_DAYS");
});
test("strong positive evidence across enough distinct days remains only a paper research candidate",()=>{
 const rows=dayTrades(25,.7,3);
 const result=blockBootstrap(rows,{strategyId:"ema_pullback",strategyCount:4});
 assert.ok(result.lower_bound_r>0);
 assert.equal(result.status,"POSITIVE_AFTER_MULTIPLE_TESTS");
 assert.equal(result.eligible_for_paper_research,true);
 assert.equal(result.tests_screened,4);
 assert.ok(result.effective_confidence>.98);
});
test("negative daily evidence cannot become a candidate",()=>{
 const result=blockBootstrap(dayTrades(45,-.4,2),{strategyId:"mean_reversion"});
 assert.ok(result.lower_bound_r<0);
 assert.equal(result.eligible_for_paper_research,false);
});
test("mixed and unqualified days are conservatively rejected",()=>{
 const rows=dayTrades(15,.02).map((x,i)=>({...x,rr:i%2===0?-.6:.62}));
 const result=blockBootstrap(rows,{strategyId:"breakout"});
 assert.equal(result.sample_days,15);
 assert.ok(result.lower_bound_r<0);
 assert.equal(result.eligible_for_paper_research,false);
});
test("bootstrapped lower bounds are reproducible across identical inputs",()=>{
 const rows=dayTrades(20,.3,2).map((x,i)=>({...x,rr:x.rr+(i%5-2)*.14}));
 const first=blockBootstrap(rows,{strategyId:"trend"});
 const second=blockBootstrap(rows,{strategyId:"trend"});
 assert.deepEqual(first,second);
});
test("duplicate intraday tickets cannot inflate sample day count",()=>{
 const rows=[...dayTrades(20,.2,5),...dayTrades(20,.2,5)];
 const result=blockBootstrap(rows,{strategyId:"trend"});
 assert.equal(result.sample_days,20);
 assert.equal(result.sample_trades,200);
});
test("invalid rows and invalid confidence settings are rejected or counted",()=>{
 const rows=[...dayTrades(12,.4),{entryTime:"oops",rr:2},{entryTime:iso(5),rr:NaN}];
 const out=blockBootstrap(rows);
 assert.equal(out.rejected_trades,2);
 assert.throws(()=>blockBootstrap(rows,{strategyCount:0}),/INVALID_STRATEGY_COUNT/);
 assert.throws(()=>blockBootstrap(rows,{resamples:10}),/INVALID_BOOTSTRAP_RESAMPLES/);
});
test("data fingerprint is stable, timestamp-sensitive and symbol-specific",()=>{
 const rows=[
 {timestamp:Date.UTC(2026,0,1),open:100,high:102,low:99,close:101,spread:.02,tickVolume:10},
 {timestamp:Date.UTC(2026,0,1,0,15),open:101,high:103,low:100,close:102,spread:.04,tickVolume:9}
 ];
 const a=fingerprint(rows,{symbol:"XAUUSD",timeframe:"M15",coverage:"complete"});
 const b=fingerprint(rows,{symbol:"XAUUSD",timeframe:"M15",coverage:"complete"});
 const c=fingerprint(rows,{symbol:"EURUSD",timeframe:"M15",coverage:"complete"});
 const d=fingerprint(rows.map((r,i)=>i?{...r,close:102.01}:r),{symbol:"XAUUSD",timeframe:"M15",coverage:"complete"});
 assert.equal(a.id,b.id);
 assert.notEqual(a.id,c.id);
 assert.notEqual(a.id,d.id);
 assert.equal(a.rows,2);
 assert.equal(a.algorithm,"SHA-256");
});
test("input fingerprint refuses nonchronological or nonfinite market data",()=>{
 const base={timestamp:Date.UTC(2026,0,1),open:1,high:2,low:.5,close:1.5,spread:.01};
 assert.throws(()=>fingerprint([base,base]),/BARS_NOT_STRICTLY_INCREASING/);
 assert.throws(()=>fingerprint([{...base,high:Infinity}]),/NON_FINITE_CANDLE_VALUE/);
});
test("research engine keeps execution disabled after enhanced diagnostics",()=>{
 const c=[];let p=150;
 for(let i=0;i<1100;i++){const open=p,close=open+Math.sin(i*.15)*.7+.07; c.push({
  timestamp:Date.UTC(2025,0,1)+i*900000,open,close,
  high:Math.max(open,close)+.3,low:Math.min(open,close)-.3,
  spread:.05,tickVolume:100+i%7
 });p=close;}
 const r=engine.research(c,{timeframe:"M15",coverage:"complete"});
 assert.equal(r.execution_enabled,false);
 assert.equal(r.portfolio.execution_enabled,false);
 assert.equal(r.strategies.length,4);
 for(const s of r.strategies){
  assert.equal(s.integrity.tests_screened,4);
  assert.ok(!s.integrity.eligible_for_paper_research||s.integrity.sample_days>=12);
  if(s.status==="PAPER_CANDIDATE")assert.equal(s.integrity.eligible_for_paper_research,true);
 }
});
