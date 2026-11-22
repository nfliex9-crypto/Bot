"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const p=require("../brain/portfolio-exposure-advisor.js");
const t=Date.UTC(2026,10,1),asOf=t+160*3600000;
function history(flip=1){
 return Array.from({length:140},(_,i)=>{
  const v=100*Math.exp(flip*(i*.0007+Math.sin(i*.6)*.004));
  return {time:t+i*3600000,close:v};
 });
}
const base={accountId:"fusion-demo",equity:5000,asOf,
 proposal:{accountId:"fusion-demo",symbol:"EURUSD",side:"LONG",riskAtStop:25},
 positions:[{accountId:"fusion-demo",symbol:"BTCUSD",side:"LONG",riskAtStop:25}],
 histories:{EURUSD:history(1),BTCUSD:history(1)}};
test("matched positive price co-movement dynamically reduces proposed risk",()=>{
 const a=p.assess(base);
 assert.equal(a.ready,true,JSON.stringify(a));
 assert.ok(a.riskMultiplier<1);
 assert.equal(a.observations.length,1);
 assert.equal(a.observations[0].matchedH1,139);
 assert.equal(a.grossCombinedStopExposurePct,1);
 assert.equal(a.executionApproved,false);
});
test("opposite signed correlation cannot be assumed to be negative account risk",()=>{
 const a=p.assess({...base,histories:{EURUSD:history(1),BTCUSD:history(-1)}});
 assert.equal(a.ready,true);assert.equal(a.riskMultiplier,1);
 const b=p.assess({...base,positions:[{...base.positions[0],side:"SHORT"}]});
 assert.equal(b.ready,true);assert.equal(b.riskMultiplier,1);
});
test("missing broker history or incomplete risk amount blocks proxy instead of inventing correlation",()=>{
 assert.equal(p.assess({...base,histories:{EURUSD:history(1)}}).ready,false);
 assert.equal(p.assess({...base,positions:[{...base.positions[0],riskAtStop:undefined}]}).reason,"PORTFOLIO_RISK_UNVERIFIED");
 assert.equal(p.assess({...base,positions:[{...base.positions[0],accountId:"other"}]}).ready,false);
});
test("H1 future or duplicated timestamps never count as evidence",()=>{
 const invalid=[...history(1),history(1).at(-1)];
 assert.equal(p.returns(invalid,asOf),null);
 assert.equal(p.returns(history(1),t+130*3600000),null);
});
test("spread, commission, swap and slippage columns are irrelevant to stop exposure",()=>{
 const a=p.assess(base);
 const b=p.assess({...base,
  histories:{EURUSD:history(1).map(x=>({...x,spread:9000,commission:-8000})),
    BTCUSD:history(1).map(x=>({...x,swap:-5000,slippage:5000}))}});
 assert.deepEqual(a,b);
});
test("zero open positions requires no other asset correlation",()=>{
 const a=p.assess({...base,positions:[],histories:{EURUSD:history(1)}});
 assert.equal(a.ready,true);assert.equal(a.riskMultiplier,1);
 assert.equal(a.existingRiskAtStop,0);
});
