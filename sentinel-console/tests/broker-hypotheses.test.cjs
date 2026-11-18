"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const hypotheses=require("../brain/broker-hypotheses.js");
const {normalizeBatch}=require("../brain/broker-ingestion.js");
function demoBars(n=1300){
 let p=1.08;
 return Array.from({length:n},(_,i)=>{
  const open=p,close=open+Math.sin(i*.19)*.00035;
  p=close;
  return {timestamp:Date.UTC(2026,3,1)+i*900000,open,close,
   high:Math.max(open,close)+.00015,low:Math.min(open,close)-.00015,
   spread:null,tickVolume:100+i%9};
 });
}
test("real MT5 OHLC without broker spreads generates ONLY unverified hypotheses",()=>{
 const data=demoBars(1500);
 const x=hypotheses.proxyHypotheses(data,{symbol:"EURUSD",timeframe:"M15",
  coverage:"complete",missingSpreadRatio:1});
 assert.equal(x.status,"OHLC_HYPOTHESES_ONLY");
 assert.equal(x.hypotheses.length,16);
 assert.equal(x.assumptions.broker_spread_verified,false);
 assert.equal(x.assumptions.commission_verified,false);
 assert.equal(x.reward_points,0);
 assert.equal(x.execution_enabled,false);
 assert.ok(x.hypotheses.every(c=>c.status==="UNVERIFIED_BROKER_COST_HYPOTHESIS"&&
 c.reward_points===0&&c.execution_enabled===false));
});
test("partial, short broker candles are not used for unverified hypotheses",()=>{
 assert.equal(hypotheses.proxyHypotheses(demoBars(400),{coverage:"complete"}).hypotheses.length,0);
 assert.equal(hypotheses.proxyHypotheses(demoBars(1500),{coverage:"partial"}).hypotheses.length,0);
});
test("stored MT5 hypotheses stay separate from verified broker strategy candidate tables",async()=>{
 const bars=demoBars(1500),calls=[];
 const batch={bars,coverage:"complete",truncated:false,
 quality:{missing_spread_ratio:1,rejected_rows:0,duplicate_rows:0}};
 async function sql(parts,...args){calls.push({query:parts.join("?"),args});return []}
 const out=await hypotheses.recordBrokerHypotheses(sql,{
  account:"acc_unit_demo",symbol:"EURUSD",timeframe:"M15",batch
 });
 assert.equal(out.count,16);
 assert.equal(out.reward_points,0);
 assert.equal(out.execution_enabled,false);
 assert.ok(calls.some(c=>c.query.includes("sentinel_autonomy_broker_hypotheses")));
 assert.ok(!calls.some(c=>c.query.includes("sentinel_autonomy_candidates")));
 assert.ok(!calls.some(c=>/orders|positions/.test(c.query)));
});
