"use strict";
/**
 * Research-only composites combining user-supplied PDFs and Orderflows Delta course.
 * Inputs are completed, independently reconstructed EXECUTED-TRADE Delta bars.
 * No brokerage operations, no MT5 OHLC->Delta approximation, no costs in this
 * research module. Not claimed to be verbatim instructor strategy rules.
 */
const delta=require("./delta-engine.js");
const ID_SWEEP="sweep_divergence_bos";
const ID_TREND="trend_delta_surge";
const PARAMS=Object.freeze({
 swingLookback:6,sweepLookback:12,confirmWithinBars:4,
 breakoutLookback:6,hourlyFast:20,hourlySlow:50,hourlyWarmup:70
});
function contiguous(bars){
 return bars.length>0&&bars.every((b,i)=>i===0||
  (b.openTime===bars[i-1].closeTime&&b.sessionId===bars[i-1].sessionId&&
   b.symbol===bars[i-1].symbol&&b.venue===bars[i-1].venue&&
   b.barMs===bars[i-1].barMs));
}
function hypothesis(family,side,bar,detail){
 return {family,side,signalBarTime:bar.openTime,referenceClose:bar.close,
  detail,kind:"COMPOSITE_RESEARCH_HYPOTHESIS",executionEnabled:false,
  edgeVerified:false};
}
function ema(seq,n){
 if(seq.length<n)return null;
 const k=2/(n+1);
 let value=seq.slice(0,n).reduce((a,b)=>a+b,0)/n;
 for(const v of seq.slice(n))value+=(v-value)*k;
 return value;
}
function hourlyBars(bars){
 if(!Array.isArray(bars))throw Error("BARS_REQUIRED");
 const out=[];let current=null;
 for(const b of bars){
  const bucket=Math.floor(b.openTime/3600000)*3600000;
  if(!current||current.openTime!==bucket){
   current={openTime:bucket,closeTime:bucket+3600000,open:b.open,high:b.high,
    low:b.low,close:b.close,firstTime:b.openTime,lastClose:b.closeTime,count:0};
   out.push(current);
  }
  current.high=Math.max(current.high,b.high);
  current.low=Math.min(current.low,b.low);
  current.close=b.close;current.lastClose=b.closeTime;current.count++;
 }
 // Never use an incomplete hour and never bridge a missing bar.
 const expected=3600000/bars[0].barMs;
 return out.filter(x=>x.count===expected&&x.firstTime===x.openTime&&x.lastClose===x.closeTime);
}
function hourlyBias(hourly,at,params=PARAMS){
 let end=hourly.length-1;
 while(end>=0&&hourly[end].closeTime>at)end--;
 if(end+1<params.hourlyWarmup)return 0;
 const sub=hourly.slice(end+1-params.hourlyWarmup,end+1);
 if(sub.some((h,i)=>i>0&&h.openTime!==sub[i-1].closeTime))return 0;
 const closes=sub.map(x=>x.close),fast=ema(closes,params.hourlyFast),slow=ema(closes,params.hourlySlow);
 return fast>slow?1:fast<slow?-1:0;
}
function sweepDivergenceBos(bars,index,params=PARAMS){
 const current=bars[index];
 if(!current||index<params.sweepLookback+params.confirmWithinBars+2)return null;
 for(let k=index-1;k>=Math.max(params.sweepLookback,index-params.confirmWithinBars);k--){
  const sweep=bars[k],prev=bars.slice(k-params.sweepLookback,k);
  const path=bars.slice(k,index+1);
  if(prev.length!==params.sweepLookback||!contiguous([...prev,sweep])||!contiguous(path))continue;
  const max=Math.max(...prev.map(b=>b.high)),min=Math.min(...prev.map(b=>b.low));
  const bearish=sweep.high>max&&sweep.close<max&&sweep.delta<0;
  const bullish=sweep.low<min&&sweep.close>min&&sweep.delta>0;
  if(!bearish&&!bullish)continue;
  const divergence=delta.detectDivergence(bars.slice(0,k+1),
   {swingLookback:params.swingLookback,equalTolerance:0}).signals;
  // Confirm only after the sweep and before a prior confirmation occurred.
  if(bearish&&divergence.some(s=>s.side==="SHORT")&&current.close<sweep.low&&
    current.close<current.open&&path.slice(1,-1).every(b=>b.close>=sweep.low&&b.high<=sweep.high)&&
    current.high<=sweep.high)
   return hypothesis(ID_SWEEP,"SHORT",current,
    {sweepTime:sweep.openTime,sweptLevel:max,bosLevel:sweep.low,
     deltaAtSweep:sweep.delta,barsToConfirm:index-k});
  if(bullish&&divergence.some(s=>s.side==="LONG")&&current.close>sweep.high&&
    current.close>current.open&&path.slice(1,-1).every(b=>b.close<=sweep.high&&b.low>=sweep.low)&&
    current.low>=sweep.low)
   return hypothesis(ID_SWEEP,"LONG",current,
    {sweepTime:sweep.openTime,sweptLevel:min,bosLevel:sweep.high,
     deltaAtSweep:sweep.delta,barsToConfirm:index-k});
 }
 return null;
}
function trendDeltaSurge(bars,index,hourly,params=PARAMS){
 const x=bars.slice(index-3,index+1);
 if(x.length!==4||!contiguous(x)||index<params.breakoutLookback+4)return null;
 const surge=delta.detectSurge(x);
 if(!surge.length)return null;
 const side=surge[0].side,bias=hourlyBias(hourly,bars[index].closeTime,params);
 if((side==="LONG"?1:-1)!==bias)return null;
 const previous=bars.slice(index-params.breakoutLookback,index);
 if(!contiguous([...previous,bars[index]]))return null;
 const last=bars[index];
 if(side==="LONG"&&last.close>Math.max(...previous.map(x=>x.high))&&last.close>last.open)
  return hypothesis(ID_TREND,"LONG",last,{h1Bias:"UP",surgeDeltas:x.map(b=>b.delta),
    brokenLevel:Math.max(...previous.map(b=>b.high))});
 if(side==="SHORT"&&last.close<Math.min(...previous.map(x=>x.low))&&last.close<last.open)
  return hypothesis(ID_TREND,"SHORT",last,{h1Bias:"DOWN",surgeDeltas:x.map(b=>b.delta),
    brokenLevel:Math.min(...previous.map(b=>b.low))});
 return null;
}
function signalsAt(bars,index,hourly,params=PARAMS,now=Date.now()){
 if(!Array.isArray(bars)||!Number.isSafeInteger(index)||index<0||index>=bars.length||
    bars[index].sourceQuality!==delta.QUALITY||bars[index].closed!==true||
    bars[index].closeTime>now)throw Error("VERIFIED_CLOSED_DELTA_BAR_REQUIRED");
 const x=[sweepDivergenceBos(bars,index,params),
  trendDeltaSurge(bars,index,hourly,params)].filter(Boolean);
 return x;
}
module.exports={ID_SWEEP,ID_TREND,PARAMS,hourlyBars,hourlyBias,
 sweepDivergenceBos,trendDeltaSurge,signalsAt};
