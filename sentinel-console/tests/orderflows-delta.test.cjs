"use strict";
const {test}=require("node:test"),assert=require("node:assert/strict");
const e=require("../worker/orderflow/delta-engine.js");
const NOW=Date.UTC(2026,10,21,0,10),MS=60_000;
const opts={venue:"TEST_EXCHANGE",symbol:"BTCUSD",sourceQuality:e.QUALITY,tickSize:1,barMs:MS,now:NOW};
const mk=(i,sizes,sessionId="SESSION1")=>sizes.map((size,j)=>({time:NOW-(6-i)*MS+j*1000,
 tradeId:`${sessionId}-${i}-${j}`,price:100+i,size:Math.abs(size),
 aggressorSide:size>0?"BUY":"SELL",sessionId}));
function bars(series){return e.buildBars(series.flatMap((v,i)=>mk(i,v)),opts)}
function sig(b,params={swingLookback:2,equalTolerance:0,nearExtremeTolerance:0.1}){
 return e.evaluate(b,params,NOW);
}
test("reconstructs executed-volume delta, intrabar extrema and price-level footprint",()=>{
 const b=bars([[2,-5,1]])[0];
 assert.equal(b.delta,-2);assert.equal(b.maxIntrabarDelta,2);assert.equal(b.minIntrabarDelta,-3);
 assert.equal(b.buyVolume,3);assert.equal(b.sellVolume,5);assert.equal(b.volume,8);
 assert.equal(b.priceLevels[0].delta,-2);assert.equal(b.cvd,-2);assert.equal(b.cvdOverVolume,-.25);
});
test("delta extrema are NOT max/min of closed-bar deltas",()=>{
 const b=bars([[4,-10,7]])[0];assert.equal(b.delta,1);
 assert.equal(b.maxIntrabarDelta,4);assert.equal(b.minIntrabarDelta,-6);
});
test("session CVD resets with explicit venue session, not local time",()=>{
 const t=[...mk(0,[2]),...mk(1,[-1],"SESSION2")];
 const b=e.buildBars(t,opts);assert.equal(b[0].cvd,2);assert.equal(b[1].cvd,-1);
});
test("rejects guessed tick volume, missing sides, duplicates, unsorted trades",()=>{
 assert.throws(()=>e.buildBars([{...mk(0,[1])[0],aggressorSide:"UNKNOWN"}],opts),/INVALID/);
 assert.throws(()=>e.buildBars(mk(0,[1,1]).map(x=>({...x,tradeId:"same"})),opts),/INVALID/);
 assert.throws(()=>e.buildBars([mk(1,[1])[0],mk(0,[1])[0]],opts),/INVALID/);
 assert.throws(()=>e.buildBars(mk(0,[1]),{...opts,sourceQuality:"MT5_TICK_VOLUME"}),/VERIFIED/);
});
test("surge long and short match four-bar sequence exactly",()=>{
 const long=bars([[-5],[1],[2],[3]]),short=bars([[5],[-1],[-2],[-3]]);
 assert.equal(e.detectSurge(long)[0].side,"LONG");
 assert.equal(e.detectSurge(short)[0].side,"SHORT");
 assert.deepEqual(e.detectSurge(bars([[-5],[1],[1],[3]])),[]);
});
test("divergence requires explicit swing and equal-high/low tolerance",()=>{
 const b=bars([[1],[1],[-1]]);
 assert.equal(e.detectDivergence(b).blocked,"RESEARCH_SWING_LOOKBACK_AND_EQUAL_TOLERANCE_REQUIRED");
 assert.equal(e.detectDivergence(b,{swingLookback:2,equalTolerance:0}).signals[0].side,"SHORT");
 const low=bars([[-1],[-1],[1]]); // last high is also highest, but delta positive
 assert.equal(e.detectDivergence(low,{swingLookback:2,equalTolerance:0}).signals.length,0);
});
test("flip uses intrabar max/min and requires explicit near tolerance",()=>{
 const b=bars([[-5,-1],[6,1]]);
 assert.equal(e.detectFlips(b).blocked,"RESEARCH_NEAR_EXTREME_TOLERANCE_REQUIRED");
 assert.equal(e.detectFlips(b,{nearExtremeTolerance:0}).signals[0].side,"LONG");
 const s=bars([[5,1],[-6,-1]]);
 assert.equal(e.detectFlips(s,{nearExtremeTolerance:0}).signals[0].side,"SHORT");
});
test("optional one intervening bar is not silently enabled",()=>{
 const b=bars([[-5],[1],[6]]);
 assert.equal(e.detectFlips(b,{nearExtremeTolerance:0}).signals.length,0);
 assert.equal(e.detectFlips(b,{nearExtremeTolerance:0,allowOneInterveningBar:true}).signals[0].side,"LONG");
});
test("closed-only no lookahead, venue/session continuity and no execution",()=>{
 const b=bars([[-5],[1],[2],[3]]);
 assert.equal(sig(b).executionEnabled,false);
 assert.ok(sig(b).signals.every(x=>x.executionEnabled===false&&x.edgeVerified===false));
 assert.equal(sig([{...b[0],closed:false},...b.slice(1)]).status,"DATA_BLOCKED");
 assert.equal(sig([{...b[0],sourceQuality:"MT5_OHLC"},...b.slice(1)]).status,"DATA_BLOCKED");
 assert.equal(e.detectSurge([b[0],b[1],{...b[2],sessionId:"other"},b[3]]).length,0);
});

test("lesson 3 CVD/volume balance break requires researched numerical thresholds",()=>{
 const b=bars([[2,-2],[6]]);
 assert.equal(e.detectCvdVolumeBalanceBreak(b).blocked,
  "RESEARCH_CVD_VOLUME_BALANCE_AND_STRONG_DELTA_THRESHOLDS_REQUIRED");
 const r=e.detectCvdVolumeBalanceBreak(b,{nearZeroRatioTolerance:0.01,strongDeltaThreshold:5});
 assert.equal(r.signals[0].side,"LONG");
 assert.equal(r.signals[0].executionEnabled,false);
});
test("Sentinel core exposes the course without enabling broker execution",()=>{
 const core=require("../worker/cloud-trader/core.js");
 assert.equal(core.deltaCurriculum.status().setupCount,7);
 assert.equal(core.analyzeOrderflowTape(null).status,"DATA_BLOCKED");
 const tape=[[-5],[1],[2],[3]].flatMap((v,i)=>mk(i,v));
 const report=core.analyzeOrderflowTape(tape,opts,
  {swingLookback:2,equalTolerance:0,nearExtremeTolerance:0.1},NOW);
 assert.equal(report.status,"RESEARCH_ONLY");
 assert.equal(report.executionEnabled,false);
 assert.ok(report.signals.some(s=>s.id==="delta_surge"));
});
