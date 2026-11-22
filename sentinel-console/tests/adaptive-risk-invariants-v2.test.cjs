"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const risk=require("../worker/cloud-trader/adaptive-risk.js");
const regime=require("../worker/cloud-trader/regime-intelligence.js");
const now=Date.UTC(2026,10,23,12);
function fixture(seed){
 const drift=.04+(seed%13)*.008;
 const m15=Array.from({length:120},(_,i)=>{
  const open=100+i*drift+Math.sin(i*.23+seed)*.015,close=open+drift*.9;
  return {time:now-(120-i)*900000,open,close,high:close+.09,low:open-.09};
 });
 const h1=Array.from({length:100},(_,i)=>{
  const open=90+i*drift*2+Math.sin(i*.15+seed)*.02,close=open+drift;
  return {time:now-(100-i)*3600000,open,close,high:close+.11,low:open-.11};
 });
 const signal={symbol:"XAUUSD",family:seed%2?"pdf_sweep_bos":"pdf_fvg_retest",
  side:1,bar_time:m15.at(-1).time,atr:regime.atr14(m15)};
 return {signal,m15,h1,baseRiskPct:.05+(seed%5)*.05,equity:5000,dayStartEquity:5000};
}
test("authorized risk ceiling is invariant across 200 market/strategy fixtures",()=>{
 let allowed=0;
 for(let i=0;i<200;i++){
  const f=fixture(i),a=risk.evaluate(f);
  assert.ok(Number.isFinite(a.riskPct),JSON.stringify(a));
  assert.ok(a.riskPct>=0);
  if(a.allowed){
   allowed++;
   assert.ok(a.riskPct<=f.baseRiskPct+1e-8,JSON.stringify(a));
  }
 }
 assert.ok(allowed>10,"Fixtures must actually exercise permitted signals");
});
test("exposure and account drawdown never increase approved risk",()=>{
 for(let i=0;i<80;i++){
  const f=fixture(i),base=risk.evaluate(f);
  if(!base.allowed)continue;
  const one=risk.evaluate({...f,positions:[{symbol:"EURUSD"}]});
  const five=risk.evaluate({...f,positions:Array.from({length:5},(_,j)=>({symbol:"S"+j}))});
  const draw=risk.evaluate({...f,equity:4200});
  assert.equal(one.allowed,true);assert.equal(five.allowed,true);assert.equal(draw.allowed,true);
  assert.ok(one.riskPct<=base.riskPct+1e-8);
  assert.ok(five.riskPct<=one.riskPct+1e-8);
  assert.ok(draw.riskPct<=base.riskPct+1e-8);
 }
});
