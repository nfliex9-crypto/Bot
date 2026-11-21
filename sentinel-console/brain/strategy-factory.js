"use strict";
/*
 * Sentinel Strategy Factory v1.
 * Generates reproducible parameterized rules, scores broker-history OOS data,
 * retires weak candidates and rewards strong PAPER RESEARCH, never lot size.
 * All signals are created from closed bars and filled at next bar's open.
 */
const crypto=require("node:crypto");
const core=require("./engine.js");
const {blockBootstrap}=require("./robustness.js");
const FAMILIES=["trend_pullback","donchian_breakout","rsi_reversion","atr_expansion"];
const LOOKBACK=80;
const num=x=>typeof x==="number"&&Number.isFinite(x)?x:null;
function hash(s){return crypto.createHash("sha256").update(String(s)).digest("hex").slice(0,20);}
function makeSpec(family,{fast=20,slow=50,lookback=20,rsi=24,atrTrigger=1.7,stopATR=1.5,rewardR=2,hold=24}={}){
 if(!FAMILIES.includes(family))throw Error("INVALID_FAMILY");
 const spec={family,fast,slow,lookback,rsi,atrTrigger,stopATR,rewardR,hold};
 if(!Number.isInteger(lookback)||lookback<5||lookback>50||
   !Number.isInteger(hold)||hold<4||hold>48||
   !(stopATR>=.9&&stopATR<=3)||!(rewardR>=1&&rewardR<=3.5)||
   !(rsi>=12&&rsi<=38)||!(atrTrigger>=1.2&&atrTrigger<=2.7)||
   fast!==20||slow!==50)throw Error("INVALID_RULE_PARAMETERS");
 return {...spec,id:family+"_"+hash(JSON.stringify(spec))};
}
function seeds(){
 const families=[];
 for(const stopATR of [1.2,1.5]){
  for(const rewardR of [1.5,2]){
   families.push(makeSpec("trend_pullback",{stopATR,rewardR}));
   families.push(makeSpec("donchian_breakout",{stopATR,rewardR,lookback:rewardR===1.5?16:24}));
   families.push(makeSpec("rsi_reversion",{stopATR,rewardR,rsi:rewardR===1.5?22:28}));
   families.push(makeSpec("atr_expansion",{stopATR,rewardR,atrTrigger:rewardR===1.5?1.5:1.9}));
  }
 }
 return families; // 16 fixed ideas, test-count corrected across all 16.
}
function createChildren(parents,cycleId="",maxChildren=8){
 if(!Array.isArray(parents))return [];
 const produced=[],seen=new Set();
 const ordered=parents.filter(x=>x&&FAMILIES.includes(x.family)).slice(0,maxChildren);
 for(let i=0;i<ordered.length;i++){
  const p=ordered[i],k=(parseInt(hash(cycleId+"|"+p.id).slice(0,2),16)%3)-1;
  const mods=i%2===0?{rewardR:Math.max(1,Math.min(3.5,Math.round((p.rewardR+k*.25)*100)/100))}:
   {stopATR:Math.max(.9,Math.min(3,Math.round((p.stopATR+k*.2)*100)/100))};
  const spec=makeSpec(p.family,{...p,...mods});
  if(spec.id!==p.id&&!seen.has(spec.id)){seen.add(spec.id);produced.push(spec)}
 }
 return produced;
}
function signal(spec,bars,ind,i){
 if(i<LOOKBACK||i>=bars.length-1)return 0;
 const b=bars[i],v=ind[i],prev=bars[i-1],older=ind[i-1];
 if(spec.family==="trend_pullback"){
  if(v.ema20>v.ema50&&prev.close<older.ema20&&b.close>v.ema20)return 1;
  if(v.ema20<v.ema50&&prev.close>older.ema20&&b.close<v.ema20)return -1;
 }else if(spec.family==="donchian_breakout"){
  let hi=-Infinity,lo=Infinity;
  for(let j=i-spec.lookback;j<i;j++){hi=Math.max(hi,bars[j].high);lo=Math.min(lo,bars[j].low)}
  if(v.ema20>v.ema50&&b.close>hi&&b.close>b.open)return 1;
  if(v.ema20<v.ema50&&b.close<lo&&b.close<b.open)return -1;
 }else if(spec.family==="rsi_reversion"){
  if(v.rsi<spec.rsi&&b.close<v.ema20-1.1*v.atr)return 1;
  if(v.rsi>100-spec.rsi&&b.close>v.ema20+1.1*v.atr)return -1;
 }else if(spec.family==="atr_expansion"){
  if(v.tr>older.atr*spec.atrTrigger&&b.close>prev.high&&b.close>b.open&&v.ema20>v.ema50)return 1;
  if(v.tr>older.atr*spec.atrTrigger&&b.close<prev.low&&b.close<b.open&&v.ema20<v.ema50)return -1;
 }
 return 0;
}
function simulate(bars,ind,spec,start,end){
 if(start<LOOKBACK||end>bars.length||start>=end)throw Error("INVALID_FOLD");
 const trades=[];let position=null;
 for(let i=start;i<end;i++){
  const b=bars[i];
  if(position){
   const p=position,stopHit=p.dir>0?b.low<=p.stop:b.high>=p.stop;
   const targetHit=p.dir>0?b.high>=p.target:b.low<=p.target;
   let exit=null,reason=null;
   if(stopHit){exit=p.dir>0?Math.min(b.open,p.stop):Math.max(b.open,p.stop);reason="stop";}
   else if(targetHit){exit=p.target;reason="target";}
   else if(i-p.entryIndex>=spec.hold||i===end-1){exit=b.close;reason="time";}
   if(exit!==null){
    const rr=(exit-p.entry)*p.dir/p.risk;
    if(Number.isFinite(rr))trades.push({rr,entryTime:p.entryTime,time:b.timestamp,reason});
    position=null;
   }
  }
  if(position||i>=end-1||!Number.isFinite(ind[i].atr)||ind[i].atr<=0)continue;
  const dir=signal(spec,bars,ind,i);
  if(!dir)continue;
  const next=bars[i+1],risk=ind[i].atr*spec.stopATR;
  const entry=next.open;
  position={entry,dir,entryIndex:i+1,risk,entryTime:next.timestamp,
    stop:entry-dir*risk,target:entry+dir*risk*spec.rewardR};
 }
 return trades;
}
function scoreFamily(candles,options={}){
 const norm=core.normalizeCandles(candles),bars=norm.bars,quality=norm.quality;
 const complete=options.coverage==="complete"&&options.truncated!==true;
 const allSpecs=[...seeds(),...createChildren(options.parents||[],options.cycleId||"")];
 const unique=[...new Map(allSpecs.map(s=>[s.id,s])).values()];
 const info={source:"broker_OHLC_only",coverage:options.coverage||"unknown",truncated:options.truncated===true,
    count:bars.length,score_basis:"GROSS_PRICE_ONLY_NO_TRANSACTION_COSTS",
    rejected_rows:quality.rejected_rows,sampled_candidates:unique.length};
 if(bars.length<900||!complete||
    quality.rejected_rows>0||quality.duplicate_rows>0){
  return {status:"INSUFFICIENT_REAL_HISTORY",quality:info,
   candidates:[],orders_enabled:false,reason:bars.length<900?"MIN_900_BARS_REQUIRED":
    !complete?"INCOMPLETE_PROVIDER_COVERAGE":"PRICE_HISTORY_QUALITY_WEAK"};
 }
 const indicators=core.indicators(bars),n=bars.length,validationStart=Math.floor(n*.5),heldStart=Math.floor(n*.75);
 const candidates=unique.map(spec=>{
  const validation=simulate(bars,indicators,spec,validationStart,heldStart);
  const heldout=simulate(bars,indicators,spec,heldStart,n);
  const val=core.metrics(validation),test=core.metrics(heldout);
  const bootstrap=blockBootstrap(validation,{strategyId:spec.id,
    strategyCount:unique.length,minDays:12,resamples:512});
  const testDays=new Set(heldout.map(x=>new Date(x.entryTime).toISOString().slice(0,10))).size;
  // OOS holdout must corroborate validation. Reward never changes capital/risk.
  const qualified=validation.length>=18&&heldout.length>=12&&
     bootstrap.eligible_for_paper_research&&testDays>=8&&
     val.expectancy_r>0&&test.expectancy_r>0&&test.drawdown_r<=12;
  const reject=(validation.length>=18&&val.expectancy_r<-.1)||
       (heldout.length>=12&&test.expectancy_r<-.1);
  const status=qualified?"BOOST_PAPER_RESEARCH_2X":reject?"RETIRE_PAPER_RESEARCH":"OBSERVE_MORE";
  return {id:spec.id,family:spec.family,spec,status,
    priority_multiplier:qualified?2:reject?0:1,
    validation:{trades:val.trades,expectancy_r:val.expectancy_r,drawdown_r:val.drawdown_r},
    holdout:{trades:test.trades,days:testDays,expectancy_r:test.expectancy_r,drawdown_r:test.drawdown_r},
    robustness:bootstrap,orders_enabled:false};
 });
 candidates.sort((a,b)=>b.priority_multiplier-a.priority_multiplier||
  (b.robustness.lower_bound_r??-Infinity)-(a.robustness.lower_bound_r??-Infinity));
 return {status:"RESEARCH_ONLY",quality:info,candidates,
    rewarded:candidates.filter(x=>x.priority_multiplier===2).length,
    retired:candidates.filter(x=>x.priority_multiplier===0).length,
    orders_enabled:false,risk_multiplier:1,
    caveat:"The same history is repeatedly observed across cycles; rewards are paper research priority only, not executable forward evidence."};
}
module.exports={FAMILIES,seeds,makeSpec,createChildren,signal,simulate,scoreFamily};
