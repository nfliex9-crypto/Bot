"use strict";
/**
 * Source-informed PRICE-ONLY pattern research. Never estimates true resting
 * liquidity, aggressive volume, CVD, orderbook, or broker fills from OHLC.
 * All signals at bar i depend exclusively on closed bars <=i.
 */
const curriculum=require("./pdf-curriculum.js");
const REFS=new Map(curriculum.HYPOTHESES.map(h=>[h.detector,h.refs]));
const VERSION="source-patterns-v1";
const FAMILIES=Object.freeze(["sweep_reclaim","fvg_three_candle","displacement_break"]);
const num=x=>typeof x==="number"&&Number.isFinite(x);
function normalize(raw,{now=Infinity,tfMs=900000}={}){
 if(!Array.isArray(raw)||raw.length>20000||!num(tfMs)||tfMs<=0)throw Error("INVALID_BARS_OR_TIMEFRAME");
 const bars=[];let previous=-Infinity,openExcluded=0;
 for(const b of raw){
  const time=b.timestamp;
  if(!Number.isSafeInteger(time)||time<=previous||
   ![b.open,b.high,b.low,b.close].every(num)||b.low>b.high||
   Math.min(b.open,b.close)<b.low||Math.max(b.open,b.close)>b.high||
   b.open<=0||b.low<=0)throw Error("INVALID_SOURCE_BAR");
  previous=time;
  if(time+tfMs>now){openExcluded++;continue}
  bars.push({timestamp:time,open:b.open,high:b.high,low:b.low,close:b.close});
 }
 return {bars,open_excluded:openExcluded};
}
function at(bars,i,{lookback=12,displacement=1.6,minGap=0}={}){
 if(!Array.isArray(bars)||i<Math.max(lookback,3)||i>=bars.length||
    !Number.isInteger(lookback)||lookback<5||lookback>80)throw Error("INVALID_SIGNAL_INDEX");
 const b=bars[i],c=bars[i-1],a=bars[i-2],before=bars.slice(i-lookback,i);
 const high=Math.max(...before.map(x=>x.high)),low=Math.min(...before.map(x=>x.low));
 const range=b.high-b.low,body=Math.abs(b.close-b.open);
 const avgBody=before.reduce((s,x)=>s+Math.abs(x.close-x.open),0)/before.length;
 const events=[];
 const longSweep=b.low<low&&b.close>low&&b.close<=high;
 const shortSweep=b.high>high&&b.close<high&&b.close>=low;
 if(longSweep!==shortSweep&&(longSweep||shortSweep)){
  events.push({family:"sweep_reclaim",side:longSweep?"LONG":"SHORT",
   level:longSweep?low:high,pattern:"PRIOR_EXTREME_PIERCED_AND_RECLAIMED"});
 }
 // Three-bar imbalance is a non-overlap of wick extremes. This is NOT proof
 // of an order-book liquidity void or a guarantee that the gap will be filled.
 if(b.low>a.high+minGap&&c.close>c.open){
  events.push({family:"fvg_three_candle",side:"LONG",level:a.high,
   gap:b.low-a.high,pattern:"BULLISH_THREE_BAR_WICK_NONOVERLAP"});
 }else if(b.high<a.low-minGap&&c.close<c.open){
  events.push({family:"fvg_three_candle",side:"SHORT",level:a.low,
   gap:a.low-b.high,pattern:"BEARISH_THREE_BAR_WICK_NONOVERLAP"});
 }
 if(avgBody>0&&body>=avgBody*displacement&&range>0&&body/range>=.65){
  if(b.close>high&&b.close>b.open)
   events.push({family:"displacement_break",side:"LONG",level:high,
    pattern:"STRONG_BODY_CLOSE_ABOVE_PRIOR_RANGE"});
  else if(b.close<low&&b.close<b.open)
   events.push({family:"displacement_break",side:"SHORT",level:low,
    pattern:"STRONG_BODY_CLOSE_BELOW_PRIOR_RANGE"});
 }
 return events.map(e=>({...e,time:b.timestamp,source_pages:REFS.get(e.family)||[],
  data_type:"BROKER_OHLC_PRICE_ONLY",broker_cost_verified:false,
  orderflow_verified:false,execution_enabled:false,edge_verified:false}));
}
function scanRecent(raw,{now=Date.now(),tfMs=900000,lookback=12,maxBars=240,forwardBars=4}={}){
 const norm=normalize(raw,{now,tfMs}),bars=norm.bars;
 if(!Number.isInteger(maxBars)||maxBars<60||maxBars>3000||
    !Number.isInteger(forwardBars)||forwardBars<1||forwardBars>24)throw Error("INVALID_SCAN_OPTIONS");
 if(bars.length<Math.max(lookback+3,40))return {
  version:VERSION,status:"INSUFFICIENT_CLOSED_BARS",closed_bars:bars.length,
  excluded_open_bars:norm.open_excluded,execution_enabled:false,events:[]};
 const start=Math.max(lookback,bars.length-maxBars);
 const counts=Object.fromEntries(FAMILIES.map(x=>[x,0]));
 const labeled=Object.fromEntries(FAMILIES.map(x=>[x,{count:0,sum_pct:0,positive:0}]));
 const events=[];
 for(let i=start;i<bars.length;i++){
  const found=at(bars,i,{lookback});
  for(const e of found){
   counts[e.family]++;
   events.push(e);
   // Retrospective descriptive follow-through only, never a backtest or
   // a next-bar broker fill. Signals are computed BEFORE future labels.
   if(i+forwardBars<bars.length){
    const from=bars[i+1].open,to=bars[i+forwardBars].close;
    const direction=e.side==="LONG"?1:-1;
    const pct=direction*(to-from)/from*100;
    const lab=labeled[e.family];lab.count++;lab.sum_pct+=pct;
    if(pct>0)lab.positive++;
   }
  }
 }
 return {version:VERSION,status:"PRICE_PATTERN_OBSERVATIONS_ONLY",
  closed_bars:bars.length,excluded_open_bars:norm.open_excluded,
  window_start:new Date(bars[start].timestamp).toISOString(),
  window_end:new Date(bars.at(-1).timestamp).toISOString(),
  counts,events:events.slice(-8),
  descriptive_forward_only:Object.fromEntries(FAMILIES.map(f=>{
   const v=labeled[f];
   return [f,{labeled:v.count,
    mean_signed_move_pct:v.count?Number((v.sum_pct/v.count).toFixed(5)):null,
    positive_fraction:v.count?Number((v.positive/v.count).toFixed(4)):null}];
  })),
  label_horizon_bars:forwardBars,
  warnings:["NO_HISTORICAL_BID_ASK_OR_FEES","NO_BROKER_FILL_SIMULATION",
    "NOT_OUT_OF_SAMPLE_OR_PROFITABILITY_EVIDENCE",
    "OHLC_SWEEP_IS_NOT_VERIFIED_STOP_LIQUIDITY"],
  execution_enabled:false,edge_verified:false,auto_promotion:false};
}
module.exports={VERSION,FAMILIES,normalize,at,scanRecent};
