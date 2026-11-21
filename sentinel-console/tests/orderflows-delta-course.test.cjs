"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const c=require("../brain/orderflows-delta-curriculum.js");
const e=require("../worker/orderflow/delta-engine.js");
const START=Date.UTC(2026,10,20,12),MS=60000;
const contract={source:"EXECUTED_TAPE",aggressorMethod:"EXCHANGE_AGGRESSOR_FLAG",
 venue:"TEST_VENUE",symbol:"TEST_CONTRACT"};
function trade(bar,seq,side,size,price=100,sessionId="2026-11-20"){
 return {time:START+bar*MS+1000+seq%100,sequence:seq,side,size,price,
  venue:contract.venue,symbol:contract.symbol,sessionId};
}
function aggregate(trades,extra={}){return e.aggregateTrades(trades,{
 barMs:MS,tickSize:.25,now:START+20*MS,contract,...extra});}
function onePerBar(deltas){
 const xs=deltas.map((n,i)=>trade(i,i+1,n>0?"BUY":"SELL",Math.abs(n),100+(i%2)*.25));
 return aggregate(xs).closed_bars;
}
test("five original owner videos indexed with immutable hashes and no invented words",()=>{
 assert.equal(c.validate(),true);
 assert.equal(c.SOURCES.length,5);
 assert.equal(c.SETUPS.length,7);
 assert.equal(c.SETUPS.filter(s=>s.status==="RULE_FROM_VISIBLE_SLIDE").length,3);
 assert.equal(c.SETUPS.filter(s=>s.status==="NAMED_NOT_EXPLAINED").length,4);
 assert.equal(c.status().complete_spoken_coverage,false);
 assert.equal(c.status().execution_enabled,false);
});
test("trade-by-trade maximum/minimum delta includes interim extremes and initial zero",()=>{
 const r=aggregate([trade(0,1,"BUY",2,100),trade(0,2,"SELL",5,100.25)]);
 const b=r.closed_bars[0];
 assert.equal(b.buy_volume,2);assert.equal(b.sell_volume,5);
 assert.equal(b.delta,-3);assert.equal(b.max_delta,2);assert.equal(b.min_delta,-3);
 assert.equal(b.executed_volume,7);assert.equal(b.cvd,-3);
 assert.equal(b.cvd_over_volume,-3/7);
 assert.equal(b.footprint.length,2);
 assert.equal(b.footprint[0].delta,2);
 assert.equal(b.footprint[1].delta,-5);
 assert.equal(r.execution_enabled,false);
});
test("never silently derive delta from OHLC or unsigned tick volume",()=>{
 assert.throws(()=>aggregate([{time:START,open:1,high:2,low:1,close:2,tick_volume:100}]),/INVALID_NONMONOTONIC_OR_MIXED_TAPE/);
 assert.throws(()=>aggregate([],{contract:{...contract,source:"BROKER_OHLC"}}),/EXECUTED_TAPE_PROVENANCE_REQUIRED/);
});
test("reject duplicated, out-of-order and mixed trade tape",()=>{
 assert.throws(()=>aggregate([trade(0,1,"BUY",2),trade(0,1,"SELL",2)]),/INVALID_NONMONOTONIC_OR_MIXED_TAPE/);
 assert.throws(()=>aggregate([trade(1,2,"BUY",2),trade(0,3,"SELL",2)]),/INVALID_NONMONOTONIC_OR_MIXED_TAPE/);
 assert.throws(()=>aggregate([{...trade(0,1,"BUY",2),venue:"OTHER"}]),/INVALID_NONMONOTONIC_OR_MIXED_TAPE/);
 assert.throws(()=>aggregate([trade(0,1,"BUY",2,100.1)]),/TRADE_PRICE_NOT_ALIGNED_TO_TICK/);
});
test("only complete bars enter the course scanner",()=>{
 const r=aggregate([trade(0,1,"BUY",2),trade(20,2,"SELL",4)],{now:START+20*MS+3000});
 assert.equal(r.closed_bars.length,1);
 assert.equal(r.excluded_open_bars,1);
});
test("CVD correctly resets on explicitly supplied venue session boundary",()=>{
 const r=aggregate([trade(0,1,"BUY",5),trade(1,2,"SELL",3),trade(2,3,"SELL",2,100,"NEXT_SESSION")]);
 assert.equal(r.closed_bars[1].cvd,2);
 assert.equal(r.closed_bars[2].cvd,-2);
 assert.equal(r.closed_bars[2].cvd_over_volume,-1);
});
test("source-derived four-bar surge LONG and SHORT, with no order permission",()=>{
 const b=onePerBar([-2,1,3,5,9, -2,-3,-4]);
 const r=e.scan(b);
 assert.ok(r.events.some(x=>x.id==="delta_surge"&&x.side==="LONG"&&x.bar_start===b[3].start));
 assert.ok(r.events.some(x=>x.id==="delta_surge"&&x.side==="SHORT"&&x.bar_start===b[7].start));
 assert.equal(r.events.every(x=>x.execution_enabled===false),true);
});
test("a four-bar pattern across missing candles cannot count as surge",()=>{
 const b=onePerBar([-2,1,3,5]);b[2]={...b[2],start:b[2].start+MS,end:b[2].end+MS};
 assert.equal(e.scan(b).events.filter(x=>x.id==="delta_surge").length,0);
});
test("divergence requires explicit research pivot and equality convention",()=>{
 const b=onePerBar([1,-2,3,-5]);
 b[0].h=100;b[1].h=101;b[2].h=102;b[3].h=102;
 const no=e.scan(b);
 assert.ok(no.pending_configuration.includes("DIVERGENCE_PIVOT_WINDOW_EQUAL_TOLERANCE_AND_TICK_SIZE_UNSPECIFIED_BY_COURSE"));
 assert.equal(no.events.some(x=>x.id==="delta_divergence"),false);
 const r=e.scan(b,{comparisonWindow:3,equalToleranceTicks:0,tickSize:.25});
 assert.ok(r.events.some(x=>x.id==="delta_divergence"&&x.side==="SHORT"));
});
test("delta flips require real intrabar extrema and explicit near fraction",()=>{
 const b=onePerBar([-5,7]);
 assert.equal(b[0].max_delta,0);assert.equal(b[1].min_delta,0);
 assert.equal(e.scan(b).events.some(x=>x.id==="delta_flips"),false);
 const r=e.scan(b,{nearExtremeFraction:0});
 assert.ok(r.events.some(x=>x.id==="delta_flips"&&x.side==="LONG"));
 assert.equal(r.events[0].execution_enabled,false);
});
test("allowing a single intervening bar is opt-in and documented",()=>{
 const b=onePerBar([-5,1,7]);
 assert.equal(e.scan(b,{nearExtremeFraction:0}).events.filter(x=>x.id==="delta_flips").length,0);
 assert.ok(e.scan(b,{nearExtremeFraction:0,allowInterveningFlip:true}).events.some(
  x=>x.id==="delta_flips"&&x.gap_bars===1&&x.side==="LONG"));
});
test("estimated aggressor side is never described as verified venue volume",()=>{
 const r=aggregate([trade(0,1,"BUY",4)],{
  contract:{...contract,aggressorMethod:"ESTIMATED_SIDE"}});
 assert.equal(r.execution_block_reason,"ESTIMATED_AGGRESSOR_SIDE");
 assert.equal(r.closed_bars[0].source_quality,"ESTIMATED_SIDE");
 assert.equal(r.provenance.independently_verified,false);
});
test("uncalibrated setup names are never silently implemented",()=>{
 assert.deepEqual(e.scan(onePerBar([1,2])).setup_coverage.named_without_rules,
 ["delta_transition","delta_tails","delta_bulges","delta_reversal"]);
 assert.throws(()=>e.scan(onePerBar([-1,2]),{nearExtremeFraction:.9}),/INVALID_FLIP_TOLERANCE/);
});
