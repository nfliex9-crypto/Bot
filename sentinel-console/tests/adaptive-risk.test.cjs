"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const adaptive=require("../worker/cloud-trader/adaptive-risk.js");
const c=require("../worker/cloud-trader/core.js");
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
 const s={symbol:"BTCUSD",family:"pdf_sweep_bos",side:1,
   bar_time:m15.at(-1).time,reference_close:m15.at(-1).close,
   atr:adaptive.atr(m15),stop_atr:1.7,reward_r:2,weekly_priority:1};
 return {m15,h1,signal:s,equity:5000,dayStartEquity:5000,baseRiskPct:.25};
}
test("strong trend, source setup and confirmation determine dynamic risk, without exceeding the authorized 0.25% ceiling",()=>{
 const a=adaptive.evaluate(fixture());
 assert.equal(a.allowed,true,JSON.stringify(a));
 assert.ok(a.score>.44);
 assert.ok(a.riskPct>0&&a.riskPct<=.25);
 assert.equal(a.openExposureCount,0);
});
test("existing unrelated positions reduce rather than cap trade count",()=>{
 const base=fixture();
 const a=adaptive.evaluate(base);
 const b=adaptive.evaluate({...base,positions:[
  {symbol:"EURUSD"},{symbol:"XAUUSD"},{symbol:"NAS100"},{symbol:"US500"}
 ]});
 assert.equal(b.allowed,true);
 assert.equal(b.openExposureCount,4);
 assert.ok(b.riskPct<a.riskPct);
 assert.ok(b.riskPct>0);
});
test("daily equity loss scales down risk continuously without an arbitrary 1% stop",()=>{
 const b=fixture();
 const atOnePercent=adaptive.evaluate({...b,equity:4950});
 const lower=adaptive.evaluate({...b,equity:4500});
 assert.equal(atOnePercent.allowed,true);
 assert.equal(lower.allowed,true);
 assert.ok(lower.riskPct<atOnePercent.riskPct);
 assert.ok(atOnePercent.riskPct<b.baseRiskPct*2);
});
test("directional H1 trend disagreement vetoes setup",()=>{
 const b=fixture();
 const descending=b.h1.map((x,i)=>{
  const open=130-i*.16,close=open-.18;
  return {...x,open,close,high:open+.1,low:close-.15};
 });
 const result=adaptive.evaluate({...b,h1:descending});
 assert.equal(result.allowed,false);
 assert.equal(result.reason,"H1_TREND_AGAINST_SIGNAL");
});
test("unverified portfolio or mismatched candle is a hard data error",()=>{
 const b=fixture();
 assert.equal(adaptive.evaluate({...b,positions:[{}]}).reason,"PORTFOLIO_EXPOSURE_UNVERIFIED");
 assert.equal(adaptive.evaluate({...b,signal:{...b.signal,bar_time:0}}).reason,"ADAPTIVE_SIGNAL_BAR_MISMATCH");
});
test("demo lot sizing is not limited to arbitrary half lot but keeps native volume rules",()=>{
 const spec={volumeMin:.01,volumeMax:5,volumeStep:.01};
 assert.equal(c.floorVolume(2.15,spec),2.15);
 assert.equal(c.floorVolume(2.15,spec,.5),.5);
 assert.equal(c.floorVolume(12,spec),5);
});
test("position size risk still matches known broker stop distance",()=>{
 const now=Date.UTC(2026,10,23,12,0),s={symbol:"EURUSD",family:"pdf_sweep_bos",
  side:1,bar_time:now-900000,reference_close:1.2,atr:.0008,stop_atr:1.7,reward_r:2};
 const spec={volumeMin:.01,volumeMax:10,volumeStep:.01,digits:5,
  point:.00001,tickSize:.00001,tickValueAccount:1,specSource:"broker",
  tickValueCurrency:{code:"USD",source:"wire"},stopLevel:0};
 const x=c.preflight({signal:s,quote:{bid:1.2,ask:1.20006},spec,equity:5000,
  riskPct:.6,accountCurrency:"USD",now});
 assert.equal(x.ok,true,JSON.stringify(x));
 assert.ok(x.risk<=5000*.6/100*1.000001);
 assert.ok(x.request.stopLoss<1.2);
});
