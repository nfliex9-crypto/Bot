"use strict";
/*
 * Adaptive forward selector for verified, timestamped strategy attribution.
 * This module cannot place orders and its multiplier is a PAPER RESEARCH
 * scheduling weight, never a lot-size or account-risk multiplier.
 */
const {STRATEGIES,metrics}=require("./engine.js");
const ALLOWED=new Set([...STRATEGIES.map(s=>s.id),"sweep_bos_pullback"]);
function numberOrNull(v){
 if(v===null||v===undefined||v==="")return null;
 const n=Number(v);return Number.isFinite(n)?n:null;
}
function expectancy(trades){
 const values=trades.map(x=>x.netR),n=values.length;
 const avg=n?values.reduce((a,b)=>a+b,0)/n:0;
 const variance=n>1?values.reduce((s,v)=>s+(v-avg)**2,0)/(n-1):0;
 const std=Math.sqrt(variance),recent=values.slice(-20);
 const recentMean=recent.length?recent.reduce((a,b)=>a+b,0)/recent.length:0;
 const wins=values.filter(x=>x>0).reduce((a,b)=>a+b,0);
 const losses=Math.abs(values.filter(x=>x<0).reduce((a,b)=>a+b,0));
 return {count:n,mean_r:avg,lower_confidence_r:n>1?avg-1.28*std/Math.sqrt(n):null,
  early_mean_r:n?values.slice(0,Math.floor(n/2)).reduce((a,b)=>a+b,0)/Math.max(1,Math.floor(n/2)):0,
  recent_mean_r:recentMean,profit_factor:losses>0?wins/losses:null,
  raw_total_r:values.reduce((a,b)=>a+b,0)};
}
function assessForward(trades,{costStressR=.15}={}){
 if(!Array.isArray(trades))throw Error("FORWARD_TRADES_EXPECTED");
 const groups=new Map(),quality={records:trades.length,qualified:0,
  untagged:0,missing_risk:0,invalid_tags:0};
 const ordered=[...trades].sort((a,b)=>Date.parse(a.closeTime)-Date.parse(b.closeTime));
 for(const row of ordered){
  const strategy=String(row.strategyId||"");
  if(!strategy){quality.untagged++;continue}
  if(!ALLOWED.has(strategy)){quality.invalid_tags++;continue}
  const profit=numberOrNull(row.brokerProfit),risk=numberOrNull(row.riskAmount);
  if(!row.complete||profit===null||risk===null||risk<=0){quality.missing_risk++;continue}
  if(!row.taggedAt||!(Date.parse(row.taggedAt)<Date.parse(row.closeTime))) {
    quality.invalid_tags++;continue;
  }
  quality.qualified++;
  const list=groups.get(strategy)||[];
  list.push({closeTime:row.closeTime,netR:profit/risk-costStressR});
  groups.set(strategy,list);
 }
 const results=[];
 for(const strategy of ALLOWED){
  const data=groups.get(strategy)||[],m=expectancy(data);
  let status="COLLECTING_FORWARD",multiplier=1,reason="Needs at least 25 complete, pre-tagged trades";
  if(m.count>=25&&m.mean_r<-.1&&m.recent_mean_r<0&&m.profit_factor!==null&&m.profit_factor<.85){
    status="PAUSE_PAPER_RESEARCH";multiplier=0;
    reason="Persistent underperformance after conservative costs";
  }else if(m.count>=40&&m.lower_confidence_r!==null&&m.lower_confidence_r>.03&&
   m.early_mean_r>0&&m.recent_mean_r>0&&(m.profit_factor===null?m.mean_r>0:m.profit_factor>1.3)){
    status="BOOST_PAPER_RESEARCH_2X";multiplier=2;
    reason="Forward evidence positive in early and recent samples with lower-bound support";
  }else if(m.count>=25){
    status="WATCH_FORWARD";reason="Evidence neither confirms boost nor persistent loss";
  }
  results.push({strategy_id:strategy,status,relative_research_multiplier:multiplier,
   metrics:m,reason});
 }
 return {quality,strategy_results:results,orders_enabled:false,capital_risk_multiplier:1,
  note:"Relative multiplier applies ONLY to paper research priority. Broker profit may omit fees; conservative cost stress applied."};
}
function scheduleResearch(backtest,forward){
 const results=Array.isArray(backtest?.strategies)?backtest.strategies:[];
 const fw=new Map((forward?.strategy_results||[]).map(s=>[s.strategy_id,s]));
 const candidates=results.filter(x=>x.status==="PAPER_CANDIDATE");
 const weighted=candidates.map(c=>{
  const f=fw.get(c.strategy_id),multiplier=f?.relative_research_multiplier??1;
  const base=Math.max(.001,Number(c.oos?.lower_confidence_expectancy_r)||.001);
  return {strategy_id:c.strategy_id,unscaled_weight:base*multiplier,
   forward_status:f?.status||"NOT_TAGGED",reason:f?.reason||"Forward trial not available"};
 });
 const sum=weighted.reduce((v,r)=>v+r.unscaled_weight,0);
 return {mode:"PAPER_RESEARCH_ONLY",execution_enabled:false,
  allocations:weighted.map(x=>({strategy_id:x.strategy_id,
   weight:sum>0?x.unscaled_weight/sum:0,
   forward_status:x.forward_status,reason:x.reason})),
  excluded:results.filter(x=>x.status!=="PAPER_CANDIDATE").map(x=>({strategy_id:x.strategy_id,status:x.status})),
  note:"Weights are a normalized experiment schedule, not order volume or risk. 2x applies only after forward confirmation."};
}
module.exports={assessForward,scheduleResearch,ALLOWED};
