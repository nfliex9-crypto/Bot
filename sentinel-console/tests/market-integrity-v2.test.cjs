"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const {audit,check,PERIOD}=require("../worker/cloud-trader/market-integrity.js");
const now=Date.UTC(2026,10,20,12);
function data(){
 const m15=Array.from({length:100},(_,i)=>{
  const open=100+i*.03,close=open+.02;
  return {time:now-(100-i)*PERIOD.M15,open,close,high:close+.01,low:open-.01};
 });
 const byTime=new Map(m15.map(x=>[x.time,x]));
 const h1=Array.from({length:80},(_,i)=>{
  const time=now-(80-i)*PERIOD.H1;
  const sub=[0,1,2,3].map(j=>byTime.get(time+j*PERIOD.M15));
  if(sub.some(x=>!x))return {time,open:90,high:90.03,low:89.99,close:90.02};
  return {time,open:sub[0].open,close:sub[3].close,
   high:Math.max(...sub.map(x=>x.high)),low:Math.min(...sub.map(x=>x.low))};
 });
 return {m15,h1,now,brokerTickSize:.01,symbol:"XAUUSD",venue:"FUSION_MT5"};
}
test("valid closed broker M15/H1 agrees within tick tolerance",()=>{
 const x=audit(data());assert.equal(x.ok,true,JSON.stringify(x));
 assert.ok(x.comparedH1>=2);assert.equal(x.executionEnabled,false);
 assert.equal(x.evidence,"SAME_BROKER_OHLC_CROSSCHECK_NOT_EXECUTED_ORDERFLOW");
});
test("detects missing recent M15 bars instead of inventing candle continuity",()=>{
 const f=data();f.m15.splice(-5,1);
 const x=audit(f);assert.equal(x.reason,"RECENT_BAR_GAPS_UNCLASSIFIED");
 assert.equal(x.gaps.m15,1);assert.equal(x.gaps.missingM15,1);
});
test("detects missing recent H1 bars",()=>{
 const f=data();f.h1.splice(-3,1);
 const x=audit(f);assert.equal(x.reason,"RECENT_BAR_GAPS_UNCLASSIFIED");
 assert.equal(x.gaps.h1,1);
});
test("rejects H1 OHLC inconsistent with underlying broker M15 tape",()=>{
 const f=data();f.h1.at(-2).close+=.5;f.h1.at(-2).high+=.5;
 const x=audit(f);assert.equal(x.reason,"M15_H1_BROKER_PRICE_MISMATCH",JSON.stringify(x));
 assert.ok(x.tickError>2);
});
test("no verified tick size means no claim of cross-timeframe consistency",()=>{
 const x=audit({...data(),brokerTickSize:undefined});
 assert.equal(x.reason,"BROKER_TICK_SIZE_UNVERIFIED");
});
test("stale and not-yet-closed bars cannot be used as verified observations",()=>{
 const f=data();
 assert.equal(audit({...f,now:now+3*PERIOD.H1}).reason,"STALE_BROKER_FEED");
 assert.equal(audit({...f,now:now-1}).reason,"M15_INVALID_OR_UNCLOSED_BROKER_BAR");
});
test("out of order, duplicate, bad OHLC and non-grid bars fail closed",()=>{
 const f=data();
 assert.equal(check([...f.m15,f.m15.at(-1)],PERIOD.M15,now,65).ok,false);
 assert.equal(check(f.m15.map((b,i)=>i===7?{...b,low:b.high+1}:b),PERIOD.M15,now,65).ok,false);
 assert.equal(check(f.m15.map((b,i)=>i===7?{...b,time:b.time+1}:b),PERIOD.M15,now,65).ok,false);
});
