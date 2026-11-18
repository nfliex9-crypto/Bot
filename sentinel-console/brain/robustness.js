"use strict";
/**
 * Daily-block, multiple-testing-aware research validation.
 *
 * Inspired by the evidence-boundary discipline documented in ML4T, Qlib
 * and event-driven LEAN. Original standalone implementation: no code copied
 * from those repositories. NEVER infer that this is an execution signal.
 */
const DEFAULT_TESTS=4;
const DAY_MS=86400000;
const number=x=>typeof x==="number"&&Number.isFinite(x)?x:null;
function mean(values){
 return values.length?values.reduce((sum,x)=>sum+x,0)/values.length:null;
}
function seedFrom(text){
 let n=2166136261;
 for(const c of String(text)){n^=c.charCodeAt(0);n=Math.imul(n,16777619);}
 return n>>>0;
}
function rng(seed){
 let t=seed>>>0;
 return ()=>{
  t+=0x6D2B79F5;
  let z=t;z=Math.imul(z^(z>>>15),z|1);
  z^=z+Math.imul(z^(z>>>7),z|61);
  return ((z^(z>>>14))>>>0)/4294967296;
 };
}
function dayId(value){
 const t=typeof value==="number"?value:Date.parse(String(value||""));
 return Number.isFinite(t)?new Date(t).toISOString().slice(0,10):null;
}
function quantile(sorted,p){
 if(!sorted.length)return null;
 const index=Math.min(sorted.length-1,Math.max(0,p*(sorted.length-1)));
 const a=Math.floor(index),b=Math.ceil(index);
 return sorted[a]+(sorted[b]-sorted[a])*(index-a);
}
/**
 * Every trading day is treated as one observation, not every potentially
 * correlated intraday fill. Resample full day-level observations. The
 * Bonferroni-adjusted lower tail protects against screening multiple fixed
 * strategies, though it cannot correct earlier human selection of ideas.
 */
function blockBootstrap(trades,{strategyId="unknown",strategyCount=DEFAULT_TESTS,
 minDays=12,resamples=512,alpha=.05}={}){
 if(!Array.isArray(trades))throw Error("ROBUSTNESS_TRADES_MUST_BE_ARRAY");
 if(!Number.isInteger(strategyCount)||strategyCount<1||strategyCount>100)
  throw Error("INVALID_STRATEGY_COUNT");
 if(!Number.isInteger(resamples)||resamples<128||resamples>4096)
  throw Error("INVALID_BOOTSTRAP_RESAMPLES");
 if(!Number.isInteger(minDays)||minDays<4||minDays>200)throw Error("INVALID_MIN_DAYS");
 const daily=new Map();let rejected=0,accepted=0;
 for(const trade of trades){
  const day=dayId(trade?.entryTime??trade?.time);
  const r=number(trade?.rr);
  if(!day||r===null){rejected++;continue;}
  const xs=daily.get(day)||[];xs.push(r);daily.set(day,xs);accepted++;
 }
 const entries=[...daily].sort((a,b)=>a[0].localeCompare(b[0]));
 const dailyMeans=entries.map(([,xs])=>mean(xs));
 const n=dailyMeans.length,valid=n>=minDays,adjustedAlpha=alpha/strategyCount;
 const result={
  method:"daily_block_bootstrap_bonferroni_v1",
  sample_trades:accepted,sample_days:n,rejected_trades:rejected,
  tests_screened:strategyCount,adjusted_one_sided_alpha:adjustedAlpha,
  effective_confidence:1-adjustedAlpha,
  expected_daily_mean_r:mean(dailyMeans),lower_bound_r:null,
  eligible_for_paper_research:false,
  status:valid?"INCONCLUSIVE":"INSUFFICIENT_INDEPENDENT_DAYS",
  note:"Day blocks reduce intra-day dependence. Candidate screening only; NOT live execution evidence."
 };
 if(!valid)return result;
 const random=rng(seedFrom(strategyId+"|"+entries.map(x=>x[0]).join("|")+"|"+accepted));
 const boot=[];
 for(let b=0;b<resamples;b++){
  let v=0;
  for(let k=0;k<n;k++)v+=dailyMeans[Math.floor(random()*n)];
  boot.push(v/n);
 }
 boot.sort((a,b)=>a-b);
 result.lower_bound_r=quantile(boot,adjustedAlpha);
 result.eligible_for_paper_research=result.lower_bound_r>0;
 result.status=result.eligible_for_paper_research?"POSITIVE_AFTER_MULTIPLE_TESTS":"NO_ROBUST_POSITIVE_EDGE";
 return result;
}
function evaluateFamily(strategies){
 if(!Array.isArray(strategies))throw Error("ROBUSTNESS_STRATEGIES_MUST_BE_ARRAY");
 const count=strategies.length;
 return strategies.map(item=>({
  strategy_id:item.strategy_id,
  ...blockBootstrap(item.trades||[],{
   strategyId:item.strategy_id,strategyCount:count||DEFAULT_TESTS
  })
 }));
}
module.exports={blockBootstrap,evaluateFamily,seedFrom,dayId,quantile};
