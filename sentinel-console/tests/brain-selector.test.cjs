"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const {assessForward,scheduleResearch}=require("../brain/selector.js");
const time0=Date.parse("2026-09-01T00:00:00Z");
function tagged(strategyId,pnl,count,risk=100){
 return Array.from({length:count},(_,i)=>{
  const closeTime=new Date(time0+(i+1)*86400*1000).toISOString();
  return {strategyId,brokerProfit:pnl,complete:true,riskAmount:risk,
   taggedAt:new Date(time0+i*86400*1000+1500).toISOString(),closeTime};
 });
}
const taggedMixed=(strategy,count=45)=>tagged(strategy,180,count).map((x,i)=>({...x,brokerProfit:i%5===0?-70:180}));
const find=(r,name)=>r.strategy_results.find(x=>x.strategy_id===name);
test("never invent strategy identity for missing trade tags",()=>{
 const rows=Array.from({length:100},(_,i)=>({
  brokerProfit:100,complete:true,riskAmount:100,
  closeTime:new Date(time0+i*1000).toISOString()
 }));
 const r=assessForward(rows);
 assert.equal(r.quality.untagged,100);
 assert.equal(r.quality.qualified,0);
 assert.equal(find(r,"ema_pullback").relative_research_multiplier,1);
 assert.equal(r.orders_enabled,false);
});
test("retroactively assigned strategy tags are discarded",()=>{
 const close=new Date(time0+10000).toISOString();
 const r=assessForward([{strategyId:"ema_pullback",brokerProfit:100,complete:true,
  riskAmount:100,taggedAt:new Date(time0+11000).toISOString(),closeTime:close}]);
 assert.equal(r.quality.invalid_tags,1);
 assert.equal(r.quality.qualified,0);
});
test("persistent losers are paused from paper research",()=>{
 const r=assessForward(tagged("ema_pullback",-80,40));
 const x=find(r,"ema_pullback");
 assert.equal(x.status,"PAUSE_PAPER_RESEARCH");
 assert.equal(x.relative_research_multiplier,0);
 assert.equal(r.capital_risk_multiplier,1);
});
test("verified positive forward performance earns 2x relative paper research weight",()=>{
 const r=assessForward(taggedMixed("donchian_breakout",45));
 const x=find(r,"donchian_breakout");
 assert.equal(x.status,"BOOST_PAPER_RESEARCH_2X");
 assert.equal(x.relative_research_multiplier,2);
 assert.equal(r.orders_enabled,false);
});
test("strategies with too few trades cannot be doubled",()=>{
 const r=assessForward(tagged("ema_pullback",200,10));
 assert.equal(find(r,"ema_pullback").status,"COLLECTING_FORWARD");
 assert.equal(find(r,"ema_pullback").relative_research_multiplier,1);
});
test("paper schedule normalizes weights without increasing trading risk",()=>{
 const result={strategies:[
  {strategy_id:"ema_pullback",status:"PAPER_CANDIDATE",oos:{lower_confidence_expectancy_r:.2}},
  {strategy_id:"donchian_breakout",status:"PAPER_CANDIDATE",oos:{lower_confidence_expectancy_r:.2}},
  {strategy_id:"rsi_mean_reversion",status:"PAUSE_RESEARCH",oos:{lower_confidence_expectancy_r:-.1}}
 ]};
 const forward=assessForward([...taggedMixed("ema_pullback",45),
  ...tagged("donchian_breakout",50,5)]);
 const schedule=scheduleResearch(result,forward);
 assert.equal(schedule.execution_enabled,false);
 assert.equal(schedule.allocations.length,2);
 const a=schedule.allocations.find(x=>x.strategy_id==="ema_pullback");
 const b=schedule.allocations.find(x=>x.strategy_id==="donchian_breakout");
 assert.ok(a.weight>b.weight);
 assert.ok(Math.abs(a.weight+b.weight-1)<1e-10);
 assert.ok(schedule.excluded.some(x=>x.strategy_id==="rsi_mean_reversion"));
});
test("missing entry risk means outcome cannot train strategy selection",()=>{
 const rows=tagged("ema_pullback",300,80).map(x=>({...x,riskAmount:null}));
 const r=assessForward(rows);
 assert.equal(r.quality.missing_risk,80);
 assert.equal(find(r,"ema_pullback").relative_research_multiplier,1);
});

test("50 same-day wins do not qualify as independent forward evidence",()=>{
 const rows=tagged("ema_pullback",150,50).map((x,i)=>({
  ...x,
  closeTime:new Date(time0+i*60000+90000).toISOString(),
  taggedAt:new Date(time0+i*60000+1000).toISOString()
 }));
 const r=assessForward(rows),x=find(r,"ema_pullback");
 assert.equal(x.metrics.active_days,1);
 assert.notEqual(x.status,"BOOST_PAPER_RESEARCH_2X");
});
test("strategy drift pauses paper allocation even if lifetime expectancy was positive",()=>{
 const rows=tagged("ema_pullback",180,60).map((x,i)=>({...x,brokerProfit:i<45?180:-100}));
 const x=find(assessForward(rows),"ema_pullback");
 assert.equal(x.status,"PAUSE_PAPER_RESEARCH_DRIFT");
 assert.equal(x.relative_research_multiplier,0);
});
test("one giant winner cannot dominate training through outlier winsorization",()=>{
 const rows=tagged("ema_pullback",-40,45);
 rows[10].brokerProfit=1000000;
 const r=assessForward(rows),x=find(r,"ema_pullback");
 assert.equal(r.quality.clipped_outliers,1);
 assert.notEqual(x.status,"BOOST_PAPER_RESEARCH_2X");
});
test("symbol filters prevent cross-market training contamination",()=>{
 const eur=tagged("ema_pullback",-60,30).map(x=>({...x,symbol:"EURUSD"}));
 const gold=taggedMixed("ema_pullback",45).map(x=>({...x,symbol:"XAUUSD"}));
 const r=assessForward([...eur,...gold],{symbol:"XAUUSD"});
 assert.equal(r.quality.filtered_other_symbols,30);
 assert.equal(find(r,"ema_pullback").metrics.count,45);
});
test("duplicate broker ticket plus close time cannot double count outcome",()=>{
 const rows=taggedMixed("ema_pullback",45).map((x,i)=>({...x,ticket:String(1000+i)}));
 const r=assessForward([...rows,rows[3]]);
 assert.equal(r.quality.duplicates,1);
 assert.equal(find(r,"ema_pullback").metrics.count,45);
});
test("losing forward strategy is excluded from paper schedule, not given zero-weight entry",()=>{
 const b={strategies:[
  {strategy_id:"ema_pullback",family:"trend",status:"PAPER_CANDIDATE",oos:{lower_confidence_expectancy_r:.3}},
  {strategy_id:"donchian_breakout",family:"breakout",status:"PAPER_CANDIDATE",oos:{lower_confidence_expectancy_r:.2}}
 ]};
 const f=assessForward([...tagged("ema_pullback",-80,40),...taggedMixed("donchian_breakout",45)]);
 const s=scheduleResearch(b,f);
 assert.equal(s.allocations.length,1);
 assert.equal(s.allocations[0].strategy_id,"donchian_breakout");
 assert.ok(s.excluded.some(x=>x.strategy_id==="ema_pullback"));
 assert.equal(s.capital_risk_multiplier,1);
});
test("paper allocation is diversified across strategy families when available",()=>{
 const b={strategies:[
  {strategy_id:"ema_pullback",family:"trend",status:"PAPER_CANDIDATE",oos:{lower_confidence_expectancy_r:.6}},
  {strategy_id:"volatility_expansion",family:"trend",status:"PAPER_CANDIDATE",oos:{lower_confidence_expectancy_r:.3}},
  {strategy_id:"rsi_mean_reversion",family:"range",status:"PAPER_CANDIDATE",oos:{lower_confidence_expectancy_r:.1}}
 ]};
 const s=scheduleResearch(b,assessForward([]));
 const trend=s.allocations.filter(x=>x.strategy_id!=="rsi_mean_reversion").reduce((a,x)=>a+x.weight,0);
 assert.ok(trend<=.650001);
 assert.ok(Math.abs(s.allocations.reduce((a,x)=>a+x.weight,0)-1)<1e-9);
});
