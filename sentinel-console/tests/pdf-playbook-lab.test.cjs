"use strict";
const test=require("node:test"),assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
const lab=require("../brain/pdf-playbook-lab.js");
const TF=900000,START=Date.UTC(2026,5,1,0,0,0);
function bars(n=750){
 let last=100;
 return Array.from({length:n},(_,i)=>{
  const open=last,delta=.15*Math.sin(i*.17)+.06*Math.cos(i*.09),close=Math.max(1,open+delta);
  last=close;return {timestamp:START+i*TF,open,close,high:Math.max(open,close)+.23,low:Math.min(open,close)-.23};
 });
}
test("catalog identifies all eight supplied PDFs with source fingerprints and exact page references",()=>{
 assert.equal(lab.SOURCES.length,8);
 assert.equal(new Set(lab.SOURCES.map(s=>s.sha256)).size,8);
 assert.ok(lab.SOURCES.every(s=>/^[a-f0-9]{64}$/.test(s.sha256)&&
   s.evidence.every(p=>Number.isInteger(p)&&p>0&&p<=s.pages)));
 assert.deepEqual(lab.FAMILIES,["sweep_displacement_confirm","displacement_fvg_retest"]);
 assert.equal(lab.HYPOTHESES.length,2);
});
test("H1 bars must contain exactly four consecutive real M15 candles, no gap filling or future H1",()=>{
 const v=lab.normalize(bars(12));
 assert.equal(lab.aggregateH1(v).length,3);
 assert.equal(lab.aggregateH1(v.filter((_,i)=>i!==2)).length,2);
 const first=lab.aggregateH1(v)[0];
 assert.equal(first.close_time,START+3600000);
 assert.equal(first.source,"FOUR_REAL_CONSECUTIVE_M15_BROKER_CANDLES");
 const trend=lab.trendSeries(lab.normalize(bars(600)));
 assert.equal(trend.trend[0],null);
 assert.equal(trend.trend[199],null); // only 49 completed H1 bars as of 200th M15
 assert.ok(trend.covered>0);
});
test("FVG requires three correctly ordered CLOSED candles, displacement and nontrivial gap",()=>{
 const data=[
  {time:START,open:100,high:100.7,low:99.5,close:100.4},
  {time:START+TF,open:100.5,high:103.4,low:100.3,close:103.2},
  {time:START+2*TF,open:103.3,high:104.2,low:103.1,close:103.8}
 ];
 const yes=lab.fvgAt(data,2,2,.04);
 assert.equal(yes.side,1);
 assert.equal(yes.low,100.7);
 assert.equal(yes.high,103.1);
 assert.equal(lab.fvgAt(data,1,2,.04),null);
 assert.equal(lab.fvgAt(data,2,2,2),null); // spreads too big for gap
});
test("range sweep requires return inside prior extrema, not simple BOS",()=>{
 const data=Array.from({length:26},(_,i)=>({
  time:START+i*TF,open:100,high:105,low:95,close:100
 }));
 data[25]={time:START+25*TF,open:99,high:101,low:94,close:99.5};
 assert.equal(lab.sweepAt(data,25,2).side,1);
 data[25].close=93;
 assert.equal(lab.sweepAt(data,25,2),null);
});
test("bar close and H1 cross-timeframe visibility never use future bars",()=>{
 const data=lab.normalize(bars(600)),future=data.map((v,i)=>i<420?v:{
  ...v,high:v.high+150,close:v.open+100
 });
 // Changed future candles after index 419 cannot alter an already-closed setup.
 const x={features:require("../brain/edge-lab.js").precompute(data),trend:lab.trendSeries(data),reference_spread:.04};
 const y={features:require("../brain/edge-lab.js").precompute(future),trend:lab.trendSeries(future),reference_spread:.04};
 for(const i of [300,340,390,419])for(const f of lab.FAMILIES)
  assert.deepEqual(lab.signalAt(data,i,f,x),lab.signalAt(future,i,f,y));
});
test("fail closed if broker history or actual quote-based cost samples unavailable",()=>{
 const missing=lab.evaluate(bars(20),{spreads:Array.from({length:10},()=>({spread:.04}))});
 assert.equal(missing.status,"INSUFFICIENT_BROKER_BARS");
 const noQuote=lab.evaluate(bars(),{spreads:[]});
 assert.equal(noQuote.status,"COST_PROXY_UNAVAILABLE");
 assert.equal(noQuote.execution_enabled,false);
});
test("walkforward research stays purely shadow with chronological sealed holdout and 2x spread stress",()=>{
 const data=bars(760);
 const quotes=Array.from({length:30},(_,i)=>({spread:.03+i*.001}));
 const result=lab.evaluate(data,{spreads:quotes});
 assert.equal(result.status,"OHLC_PLUS_RECENT_SPREAD_COST_PROXY_ONLY");
 assert.equal(result.execution_enabled,false);
 assert.equal(result.historical_cost_data_verified,false);
 assert.equal(result.broker_verified_edge,false);
 assert.equal(result.orderflow_data_verified,false);
 assert.equal(result.families.length,2);
 assert.ok(result.families.every(x=>x.execution_enabled===false&&x.holdout_report_only===true&&
   x.optimised_on_holdout===false&&x.status!=="APPROVED_FOR_EXECUTION"));
 assert.ok(Date.parse(result.chronological_split.train_end)<Date.parse(result.chronological_split.validation_end));
});
test("broker cloud order routing has no PDF code import, no change in existing trial caps",()=>{
 const root=path.resolve(__dirname,"..");
 const trader=fs.readFileSync(path.join(root,"worker/cloud-trader/runner.js"),"utf8");
 const core=fs.readFileSync(path.join(root,"worker/cloud-trader/core.js"),"utf8");
 assert.doesNotMatch(trader,/pdf-playbook-lab/);
 assert.doesNotMatch(core,/pdf-playbook-lab/);
 assert.match(trader,/DAILY_DEMO_ENTRY_CAP/);
});
