"use strict";
/**
 * Sentinel PDF Playbook Research V1.
 *
 * Independent falsifiable hypothesis engine informed by eight owner-supplied
 * educational PDFs, with exact document fingerprints/page provenance.
 * This is NOT a copied discretionary strategy or a self-trained LLM.
 *
 * All execution remains strictly disabled. We do not know historical bid/ask,
 * true stops, order book, institutions' intent or market maker motivations.
 */
const edge=require("./edge-lab.js");
const VERSION="pdf-playbook-2026-11-20-v1";
const TF=900000,HOUR=3600000;
const FAMILIES=Object.freeze(["sweep_displacement_confirm","displacement_fvg_retest"]);
const SOURCES=Object.freeze([
 {id:"entry1",name:"Entry Types Continuation Part 1",pages:9,sha256:"8ee899dfd5523a5a635bec640f784f7be885ac5a8ad2aa4d8ecf4facb589d828",evidence:[3,4,7,8]},
 {id:"entry2",name:"Entry Types Continuations & Liquidity Part 2",pages:7,sha256:"0e9e99b0b67c5b31ad5e86a39c7798b03a616ab8ddf8eaf8fa0be088ea52c94b",evidence:[2,3,4,6]},
 {id:"liquidity_types",name:"Types of Liquidity",pages:12,sha256:"47343ffe5cbeb05543897d2cf0ec4d5ba2ef86be6f026726a65da7845dd3494b",evidence:[1,3,5]},
 {id:"imbalances",name:"Price Action Imbalance",pages:22,sha256:"7cbab3843e95f1997df3c003e83d88b49f800cc3d78d70b5a3d49cb5bf9262ff",evidence:[2,3,11]},
 {id:"supply",name:"Supply and Demand",pages:18,sha256:"1a63b9dda4dae212add35c1e5f131395b2dbe8faf5ef608e9a058233658f877c",evidence:[2,3,5,11]},
 {id:"manipulation",name:"Liquidity and Manipulation",pages:20,sha256:"940fc09f78255d031e700b0a07eac4dfd2095b3143e4844883a39582224e657e",evidence:[2,3,4]},
 {id:"ict_mmm",name:"Forex ICT & MMM Notes by Reginald Mmari",pages:109,sha256:"7a776c6a1e50aace0c95c9920785938876c07114f15f6187cc924352635ae680",evidence:[8,28,34,44,55,72,73]},
 {id:"wade_fx",name:"Market Structure and Powerful Setups by Wade FX",pages:153,sha256:"b56f668a6f534f2c14f9a03fa526b64d9c9a8be9fd4e56ee90cdb035dee75331",evidence:[9,80,81,82,104,105]}
].map(x=>Object.freeze(x)));
const HYPOTHESES=Object.freeze([
 {family:FAMILIES[0],sources:["liquidity_types:3","manipulation:3","entry2:3","wade_fx:80","entry1:4"],
  rationale:"Sweep prior range then reclaim; wait for closed-bar displacement in matching HTF direction, not instant countertrend limit fill"},
 {family:FAMILIES[1],sources:["imbalances:2","supply:5","ict_mmm:34","entry1:4","wade_fx:105"],
  rationale:"Three-candle price gap formed by a genuine displacement, untouched retest with HTF confirmation; require closed-bar evidence"}
].map(x=>Object.freeze(x)));
function normalize(raw){return edge.normalize(raw)}
function aggregateH1(bars){
 const out=[],bucket=[];
 let hour=null;
 function flush(){
  if(bucket.length!==4)return;
  const first=bucket[0].time;
  if(first%HOUR!==0||bucket.some((b,i)=>b.time!==first+i*TF))return;
  out.push({time:first,close_time:first+HOUR,open:bucket[0].open,
    high:Math.max(...bucket.map(b=>b.high)),
    low:Math.min(...bucket.map(b=>b.low)),close:bucket[3].close,
    source:"FOUR_REAL_CONSECUTIVE_M15_BROKER_CANDLES"});
 }
 for(const bar of bars){
  const current=Math.floor(bar.time/HOUR)*HOUR;
  if(hour!==null&&current!==hour){flush();bucket.length=0}
  hour=current;
  bucket.push(bar);
 }
 flush();
 return out;
}
function trendSeries(bars){
 const hourly=aggregateH1(bars),data=edge.precompute(hourly);
 const result=Array(bars.length).fill(null);
 let h=-1,valid=0;
 for(let i=0;i<bars.length;i++){
  const close=bars[i].time+TF;
  while(h+1<hourly.length&&hourly[h+1].close_time<=close)h++;
  if(h>=49&&data.e20[h]!==null&&data.e50[h]!==null){
   const gap=data.e20[h]-data.e50[h],denom=hourly[h].close;
   result[i]=Math.abs(gap)/denom<.0001?0:Math.sign(gap);
   valid++;
  }
 }
 return {hourly,trend:result,covered:valid,bars:bars.length};
}
function bodyRatio(b){return Math.abs(b.close-b.open)/Math.max(1e-12,b.high-b.low)}
function rollingLevel(bars,start,end,side){
 if(start<0||end<=start)return null;
 let v=side===1?-Infinity:Infinity;
 for(let k=start;k<end;k++)v=side===1?Math.max(v,bars[k].high):Math.min(v,bars[k].low);
 return Number.isFinite(v)?v:null;
}
/** Three-candle imbalance becomes observable only once bar j closes. */
function fvgAt(bars,j,atr,spread=0){
 if(j<2||j>=bars.length||!(atr>0))return null;
 const a=bars[j-2],m=bars[j-1],c=bars[j];
 const longGap=c.low-a.high,shortGap=a.low-c.high;
 const floor=Math.max(atr*.04,spread*2);
 const displacement=bodyRatio(m)>=.60&&
   (m.high-m.low)>=atr*.85;
 if(!displacement)return null;
 if(longGap>floor&&m.close>m.open)
  return {side:1,low:a.high,high:c.low,formed:j,mid:(c.low+a.high)/2};
 if(shortGap>floor&&m.close<m.open)
  return {side:-1,low:c.high,high:a.low,formed:j,mid:(c.high+a.low)/2};
 return null;
}
function sweepAt(bars,j,atr){
 if(j<25||!(atr>0))return null;
 const b=bars[j],priorH=rollingLevel(bars,j-20,j,1),priorL=rollingLevel(bars,j-20,j,-1);
 const height=Math.max(1e-12,b.high-b.low);
 if(b.high>priorH+atr*.04&&b.close<priorH&&
    (b.high-Math.max(b.open,b.close))/height>=.30)
  return {side:-1,level:priorH,bar:j};
 if(b.low<priorL-atr*.04&&b.close>priorL&&
    (Math.min(b.open,b.close)-b.low)/height>=.30)
  return {side:1,level:priorL,bar:j};
 return null;
}
function signalAt(bars,i,family,ctx){
 if(i<75||i>=bars.length||!FAMILIES.includes(family))return null;
 const atr=ctx?.features?.atr?.[i],direction=ctx?.trend?.trend?.[i];
 if(!(atr>0)||direction===null||direction===undefined||direction===0)return null;
 const b=bars[i],strength=(b.high-b.low)/atr;
 let reason=null,confirmBar=-1;
 if(family===FAMILIES[0]){
  // Detect an earlier "raid", then require a NEW directional bar after it.
  for(let j=i-1;j>=Math.max(25,i-5);j--){
   const previousAtr=ctx.features.atr[j],sweep=sweepAt(bars,j,previousAtr);
   if(!sweep||sweep.side!==direction)continue;
   // No entry on the sweep itself: close past the sweep bar AND 3 prior closes.
   const closeBreak=direction===1?
     b.close>Math.max(bars[j].high,...bars.slice(Math.max(j+1,i-3),i).map(x=>x.high)):
     b.close<Math.min(bars[j].low,...bars.slice(Math.max(j+1,i-3),i).map(x=>x.low));
   if(!closeBreak||strength<1.05||bodyRatio(b)<.6||
      (direction===1&&b.close<=b.open)||(direction===-1&&b.close>=b.open))continue;
   reason="SWEEP_RECLAIM_WITH_CLOSED_DISPLACEMENT";confirmBar=j;break;
  }
 } else {
  // An untouched FVG retest; closes on correct side of the midpoint, never
  // assumes passive fills at FVG before the bar is closed.
  for(let j=i-1;j>=Math.max(50,i-10);j--){
   const atrJ=ctx.features.atr[j],gap=fvgAt(bars,j,atrJ,ctx.reference_spread);
   if(!gap||gap.side!==direction||j+1>=i)continue;
   const tapped=direction===1?b.low<=gap.high&&b.high>=gap.low:
      b.high>=gap.low&&b.low<=gap.high;
   if(!tapped)continue;
   // Require first untouched return; previous touch invalidates hypothesis.
   let untouched=true;
   for(let k=j+1;k<i;k++){
    if(bars[k].low<=gap.high&&bars[k].high>=gap.low){untouched=false;break}
   }
   if(!untouched)continue;
   if(direction===1?b.close<=gap.mid||b.close<=b.open:
      b.close>=gap.mid||b.close>=b.open)continue;
   reason="UNTOUCHED_DISPLACEMENT_FVG_RETEST";confirmBar=j;break;
  }
 }
 return reason?{family,side:direction,signal_time:b.time,atr,regime:"HTF_EMA20_50",
   source_bar:confirmBar,reason,valid_at:new Date(b.time+TF).toISOString(),
   htf_source:"CLOSED_H1_AGGREGATED_FROM_BROKER_M15"}:null;
}
function evaluate(raw,{spreads=[],minBars=600}={}){
 const bars=normalize(raw);
 const base={version:VERSION,source_documents:SOURCES.length,source_sha256:SOURCES.map(s=>s.sha256),
   execution_enabled:false,broker_verified_edge:false,backtest_only:true,
   orderflow_data_verified:false,depth_data_verified:false,
   historical_cost_data_verified:false};
 if(bars.length<minBars)return {...base,status:"INSUFFICIENT_BROKER_BARS",bars:bars.length,families:[]};
 const p90=edge.costPriceFromQuotes(spreads);
 if(!(p90>0))return {...base,status:"COST_PROXY_UNAVAILABLE",bars:bars.length,families:[]};
 const features=edge.precompute(bars),trend=trendSeries(bars);
 const ctx={features,trend,reference_spread:p90};
 const splits=[Math.floor(bars.length*.6),Math.floor(bars.length*.8)];
 const cut=[bars[splits[0]].time,bars[splits[1]].time];
 const families=[];
 for(const family of FAMILIES){
  const sections={train:[],validation:[],holdout:[]},stressed=[];
  let lastExit=-1;
  for(let i=75;i<bars.length-9;i++){
   if(bars[i].time<=lastExit)continue;
   const signal=signalAt(bars,i,family,ctx);
   if(!signal)continue;
   const trade=edge.resolve(bars,i,signal,p90,8);
   if(!trade)continue;
   const section=trade.entry_time<cut[0]?"train":trade.entry_time<cut[1]?"validation":"holdout";
   if((section==="train"&&trade.exit_time>=cut[0])||
      (section==="validation"&&trade.exit_time>=cut[1]))continue;
   sections[section].push(trade);
   if(section==="validation"){
    const stressedTrade=edge.resolve(bars,i,signal,p90*2,8);
    if(stressedTrade)stressed.push(stressedTrade);
   }
   lastExit=trade.exit_time;
  }
  const train=edge.stats(sections.train),validation=edge.stats(sections.validation);
  const holdout=edge.stats(sections.holdout),validationStress=edge.stats(stressed);
  const qualifies=train.trades>=30&&validation.trades>=15&&
    train.expectancy_r>0&&validation.expectancy_r>0&&
    (validationStress.expectancy_r??-Infinity)>0;
  families.push({family,status:qualifies?"MANUAL_SHADOW_REVIEW_ONLY":"RESEARCH_NOT_PROVEN",
    train,validation,holdout,validation_stressed:validationStress,
    execution_enabled:false,holdout_report_only:true,optimised_on_holdout:false});
 }
 return {...base,status:"OHLC_PLUS_RECENT_SPREAD_COST_PROXY_ONLY",
   bars:bars.length,closed_hourly_bars:trend.hourly.length,
   higher_tf_coverage: Number((trend.covered/bars.length).toFixed(4)),
   reference_spread_p90:p90,stress_multiple:2,
   guidance:"No M1 extrapolation, true book depth, tick delta, or historic fills. ATR stop and next-M15-bar broker OHLC proxy; fees/slippage still incomplete.",
   chronological_split:{train_end:new Date(cut[0]).toISOString(),
     validation_end:new Date(cut[1]).toISOString()},
   families};
}
module.exports={VERSION,FAMILIES,SOURCES,HYPOTHESES,normalize,aggregateH1,trendSeries,
 bodyRatio,rollingLevel,fvgAt,sweepAt,signalAt,evaluate};
