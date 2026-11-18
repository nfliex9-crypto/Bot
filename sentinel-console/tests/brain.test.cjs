"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const brain=require("../brain/engine.js");
function fixture(count=900,{missingSpread=false,trend=true}={}){
 const out=[];let last=100;
 for(let i=0;i<count;i++){
  const movement=trend?(i%11===0?-.7:.18):Math.sin(i*.3)*.5;
  const open=last,close=Math.max(1,open+movement);
  const high=Math.max(open,close)+.25,low=Math.min(open,close)-.24;
  out.push({timestamp:1760000000+i*900,open,high,low,close,
    spread:missingSpread?null:.03,tickVolume:100+i%17});
  last=close;
 }
 return out;
}
test("rejects malformed candles and deduplicates identical bar timestamps",()=>{
 const bars=fixture(350);
 const result=brain.normalizeCandles([...bars,bars[4],{timestamp:12,open:20,high:10,low:8,close:15}]);
 assert.equal(result.bars.length,350);
 assert.equal(result.quality.rejected_rows,1);
 assert.equal(result.quality.duplicate_rows,1);
 assert.equal(result.quality.missing_spread_rows,0);
});
test("closed MT5 history needs broker complete=true and never guesses strategy",()=>{
 const t=brain.normalizeClosedTrade({
  ticket:"4072808150",symbol:"GOLD",side:"BUY",openPrice:4200,closePrice:4210,
  openTime:"2026-11-15T09:00:00Z",closeTime:"2026-11-15T10:00:00Z",
  profit:120.5,swap:0,commission:0,complete:true,comment:"ema_pullback"});
 assert.equal(t.complete,true);
 assert.equal(t.brokerProfit,120.5);
 assert.equal(t.strategyId,null);
 assert.equal(t.attribution,"unattributed");
 const p=brain.normalizeClosedTrade({ticket:"2",symbol:"XAUUSD",closeTime:"2026-11-15T10:00:00Z",
  profit:0,complete:false});
 assert.equal(p.brokerProfit,null);
});
test("real broker P&L summary is independent of invented strategy labels",()=>{
 const ts=[{complete:true,brokerProfit:30,strategyId:null},
   {complete:true,brokerProfit:-10,strategyId:null},
   {complete:false,brokerProfit:null,strategyId:null}];
 const result=brain.reviewRealTrades(ts);
 assert.equal(result.completed_records,2);
 assert.equal(result.unattributed_records,2);
 assert.equal(result.recorded_broker_profit,20);
 assert.equal(result.win_rate,.5);
 assert.equal(result.profit_factor,3);
});
test("no future-price leakage in EMA, ATR, RSI and historic signal prefix",()=>{
 const bars=brain.normalizeCandles(fixture(600)).bars;
 const future=fixture(40).map((b,i)=>({...b,timestamp:bars.at(-1).timestamp+(i+1)*900,
  close:10000+i*100,open:10000+i*100,high:10000+i*100+50,low:10000+i*100-50}));
 const a=brain.indicators(bars),b=brain.indicators([...bars,...future]);
 for(let i=61;i<bars.length-2;i+=37){
  assert.deepEqual(a[i],b[i]);
  for(const strat of brain.STRATEGIES){
   assert.equal(brain.signal(strat.id,bars,a,i),brain.signal(strat.id,[...bars,...future],b,i));
  }
 }
});
test("uses exactly three ordered, disjoint out-of-sample periods",()=>{
 const r=brain.research(fixture(950),{coverage:"complete",truncated:false});
 assert.equal(r.strategies.length,4);
 assert.equal(r.execution_enabled,false);
 for(const strategy of r.strategies){
  assert.equal(strategy.folds.length,3);
  const folds=strategy.folds;
  assert.ok(Date.parse(folds[0].end)<Date.parse(folds[1].start));
  assert.ok(Date.parse(folds[1].end)<Date.parse(folds[2].start));
  assert.equal(strategy.oos.trades,folds.reduce((s,v)=>s+v.trades,0));
  assert.ok(Number.isFinite(strategy.oos.expectancy_r));
 }
});
test("incomplete source data cannot promote a strategy",()=>{
 const r=brain.research(fixture(1000),{coverage:"partial",truncated:true,stopReason:"deadline"});
 assert.equal(r.portfolio.candidate_count,0);
 assert.ok(r.strategies.every(x=>x.status==="DATA_INCOMPLETE"));
});
test("missing spread history cannot promote a strategy",()=>{
 const r=brain.research(fixture(1000,{missingSpread:true}),{coverage:"complete",truncated:false});
 assert.equal(r.portfolio.candidate_count,0);
 assert.ok(r.strategies.every(x=>x.status==="COST_DATA_WEAK"));
});
test("small candle samples cannot produce a trained strategy",()=>{
 const r=brain.research(fixture(250),{coverage:"complete",truncated:false});
 assert.equal(r.portfolio.status,"NO_DATA");
 assert.deepEqual(r.strategies,[]);
});
test("paper-only research allocation never enables actual execution",()=>{
 const r=brain.research(fixture(1000),{coverage:"complete",truncated:false});
 assert.equal(r.execution_enabled,false);
 assert.equal(r.portfolio.execution_enabled,false);
 const weights=Object.values(r.portfolio.weights);
 if(weights.length)assert.ok(weights.reduce((a,b)=>a+b,0)<1.01);
 assert.ok(r.strategies.every(x=>x.relative_research_priority>=0));
});
test("intelligence code makes no requests to order execution routes",()=>{
 const src=fs.readFileSync(path.join(__dirname,"../api/brain.js"),"utf8");
 assert.doesNotMatch(src,/\/orders["'\x60]/);
 assert.doesNotMatch(src,/place_order|order_send|placeOrder/);
 assert.match(src,/DEMO_ACCOUNT_REQUIRED/);
});
