"use strict";
const test=require("node:test"),assert=require("node:assert/strict");
const lab=require("../brain/edge-lab.js");
const TF=900000;
function bars(n=600){
 let last=100;
 return Array.from({length:n},(_,i)=>{
  const open=last,drift=(Math.sin(i*.17)+Math.cos(i*.087))*.16;
  const close=Math.max(1,open+drift),high=Math.max(open,close)+.25,low=Math.min(open,close)-.25;
  last=close;
  return {timestamp:Date.UTC(2026,8,1)+i*TF,open,high,low,close};
 });
}
test("Grok-derived research does not import credentials or enable broker orders",()=>{
 const x=lab.evaluate(bars(),{spreads:Array.from({length:20},()=>({spread:.05}))});
 assert.equal(x.version,lab.VERSION);
 assert.equal(x.status,"COST_PROXY_RESEARCH_ONLY");
 assert.equal(x.execution_enabled,false);
 assert.equal(x.broker_verified_edge,false);
 assert.deepEqual(x.families.map(f=>f.family),["sweep_reclaim","compression_breakout","fvg_retest"]);
 assert.ok(x.families.every(f=>f.execution_enabled===false&&f.holdout_is_report_only===true));
 assert.match(x.cost_notice,/not historical bid\/ask/);
});
test("hard fail without genuine bid ask source instead of assuming zero friction",()=>{
 assert.equal(lab.evaluate(bars(),{spreads:[]}).status,"MISSING_REAL_SPREAD_SAMPLE");
 assert.equal(lab.evaluate(bars(80),{spreads:Array.from({length:12},()=>({spread:.05}))}).status,"INSUFFICIENT_BARS");
 assert.equal(lab.costPriceFromQuotes(Array.from({length:4},()=>({spread:.05}))),null);
});
test("cached features reproduce direct causal indicators at any closed bar",()=>{
 const data=lab.normalize(bars(220)),cache=lab.precompute(data);
 for(const i of [100,130,175,219]){
  assert.ok(Math.abs(cache.atr[i]-lab.atrAt(data,i))<1e-10);
  assert.ok(Math.abs(cache.e20[i]-lab.emaAt(data,i,20))<1e-10);
  assert.ok(Math.abs(cache.e50[i]-lab.emaAt(data,i,50))<1e-10);
  assert.deepEqual(lab.signalAt(data,i,"sweep_reclaim",cache),lab.signalAt(data,i,"sweep_reclaim"));
  assert.deepEqual(lab.signalAt(data,i,"compression_breakout",cache),lab.signalAt(data,i,"compression_breakout"));
  assert.deepEqual(lab.signalAt(data,i,"fvg_retest",cache),lab.signalAt(data,i,"fvg_retest"));
 }
});
test("bar parsing rejects nonmonotonic, corrupt OHLC and timestamps",()=>{
 const data=bars(6);
 assert.throws(()=>lab.normalize([...data,data[0]]),/INVALID_BROKER_BAR/);
 assert.throws(()=>lab.normalize([{...data[0],low:data[0].high+1}]),/INVALID_BROKER_BAR/);
 assert.throws(()=>lab.normalize([{...data[0],timestamp:"2026-09-01T00:00:00Z"}]),/INVALID_BROKER_BAR/);
});
test("signals use only closed bars at or before signal; changing future does not change signal",()=>{
 const data=lab.normalize(bars(180)),base=data.slice(0,160);
 const mutated=[...base,...data.slice(160).map(x=>({...x,close:x.open+100,high:x.open+100,low:x.open-.5}))];
 for(const family of lab.FAMILY){
  for(const i of [100,115,140,159])
   assert.deepEqual(lab.signalAt(data,i,family),lab.signalAt(mutated,i,family));
 }
});
test("entry occurs at NEXT bar; ambiguous TP/SL hits always lose",()=>{
 const start=Date.UTC(2026,8,1);
 const data=[
  {time:start,open:100,high:100.3,low:99.8,close:100},
  {time:start+TF,open:100,high:112,low:90,close:101}
 ];
 const t=lab.resolve(data,0,{side:1,family:"compression_breakout",signal_time:start,atr:2,regime:"TREND"},.1,1);
 assert.equal(t.r,-1);
 assert.equal(t.entry_time,start+TF);
 assert.equal(t.exit_reason,"AMBIGUOUS_STOP_FIRST");
 assert.equal(t.fill_quality,"BROKER_OHLC_PROXY_STOP_FIRST");
 assert.equal(lab.resolve([{...data[0]}, {...data[1],time:start+2*TF}],0,
  {side:1,family:"compression_breakout",signal_time:start,atr:2,regime:"TREND"},.1,1),null);
});
test("chronological windows, cost stress and no execution permission across results",()=>{
 const a=lab.evaluate(bars(900),{spreads:Array.from({length:30},(_,i)=>({spread:.03+i*.001}))});
 const b=lab.evaluate(bars(900),{spreads:Array.from({length:30},(_,i)=>({spread:.03+i*.001}))});
 assert.deepEqual(a,b);
 assert.ok(Date.parse(a.split.train_end)<Date.parse(a.split.validation_end));
 assert.ok(a.families.every(x=>x.train.trades>=0&&x.validation.trades>=0&&x.holdout.trades>=0));
 assert.ok(a.families.every(x=>x.status!=="APPROVED_FOR_EXECUTION"));
});
