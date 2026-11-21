"use strict";
/**
 * Orderflows Delta Trading Course: deterministic research implementation.
 * Input MUST be executed trades with an authenticated aggressor side.
 * It never places orders and NEVER substitutes MT5 OHLC/tick_volume for delta.
 * Source details and unknown parameters: brain/orderflows-delta-curriculum.js.
 */
const QUALITY="VERIFIED_AGGRESSOR_TRADES";
const finite=x=>typeof x==="number"&&Number.isFinite(x);
const nearZero=x=>Math.abs(x)<=1e-8;
function requireTape(trades,opts){
 if(!Array.isArray(trades)||!trades.length)throw Error("NO_EXECUTED_TRADES");
 if(opts.sourceQuality!==QUALITY||!opts.venue||!opts.symbol||
   !finite(opts.tickSize)||opts.tickSize<=0||!Number.isSafeInteger(opts.barMs)||opts.barMs<=0)
   throw Error("VERIFIED_TAPE_METADATA_REQUIRED");
}
/** Input trade: {time,tradeId,price,size,aggressorSide,sessionId}.
 * time: UTC milliseconds, sorted, duplicate timestamps permitted only for distinct IDs.
 * sessionId: explicitly assigned by venue calendar, not guessed from local timezone.
 */
function buildBars(trades,opts){
 requireTape(trades,opts);
 const {venue,symbol,tickSize,barMs}=opts;
 const now=opts.now??Date.now();
 if(!finite(now))throw Error("INVALID_CLOCK");
 let prevTime=-Infinity,prevSession=null,sessionCvd=0,sessionVolume=0,bar=null;
 const ids=new Set(),out=[];
 const flush=()=>{if(!bar)return;
  bar.priceLevels=Array.from(bar._levels.values()).sort((a,b)=>a.price-b.price);
  delete bar._levels;
  bar.cvd=sessionCvd;bar.cvdOverVolume=sessionVolume?sessionCvd/sessionVolume:0;
  bar.closed=bar.closeTime<=now;
  bar.deltaPriceDisagreement=(bar.close>bar.open&&bar.delta<0)||
    (bar.close<bar.open&&bar.delta>0);
  bar.intrabarDeltaShift=bar.maxIntrabarDelta>0&&bar.minIntrabarDelta<0?
    (bar.minIntrabarDeltaAt<bar.maxIntrabarDeltaAt?"MIN_TO_MAX":"MAX_TO_MIN"):
    "NO_TWO_SIDED_EXTREMA";
  bar.absorptionProven=false; // Divergence can suggest absorption, never prove an iceberg.
  out.push(bar);
 };
 for(const t of trades){
  if(!Number.isSafeInteger(t?.time)||t.time<prevTime||!finite(t.price)||t.price<=0||
     !finite(t.size)||t.size<=0||!["BUY","SELL"].includes(t.aggressorSide)||
     typeof t.tradeId!=="string"||!t.tradeId||ids.has(t.tradeId)||
     typeof t.sessionId!=="string"||!t.sessionId)throw Error("INVALID_OR_UNORDERED_EXECUTED_TRADE");
  const ticks=t.price/tickSize;
  if(Math.abs(ticks-Math.round(ticks))>1e-5)throw Error("PRICE_OFF_TICK_GRID");
  ids.add(t.tradeId);prevTime=t.time;
  if(prevSession!==t.sessionId){
   if(prevSession!==null&&bar){flush();bar=null;}
   prevSession=t.sessionId;sessionCvd=0;sessionVolume=0;
  }
  const openTime=Math.floor(t.time/barMs)*barMs;
  if(!bar||bar.openTime!==openTime){flush();
   bar={venue,symbol,sessionId:t.sessionId,barMs,openTime,closeTime:openTime+barMs,
    open:t.price,high:t.price,low:t.price,close:t.price,volume:0,
    buyVolume:0,sellVolume:0,delta:0,maxIntrabarDelta:0,minIntrabarDelta:0,
    maxIntrabarDeltaAt:openTime,minIntrabarDeltaAt:openTime,
    sourceQuality:QUALITY,_levels:new Map()};
  }
  const signed=t.aggressorSide==="BUY"?t.size:-t.size;
  bar.high=Math.max(bar.high,t.price);bar.low=Math.min(bar.low,t.price);bar.close=t.price;
  bar.volume+=t.size;
  if(signed>0)bar.buyVolume+=t.size;else bar.sellVolume+=t.size;
  bar.delta+=signed;
  if(bar.delta>bar.maxIntrabarDelta){bar.maxIntrabarDelta=bar.delta;bar.maxIntrabarDeltaAt=t.time;}
  if(bar.delta<bar.minIntrabarDelta){bar.minIntrabarDelta=bar.delta;bar.minIntrabarDeltaAt=t.time;}
  sessionCvd+=signed;sessionVolume+=t.size;
  const tick=Math.round(t.price/tickSize),price=Number((tick*tickSize).toFixed(10));
  let level=bar._levels.get(tick);
  if(!level){level={price,buyVolume:0,sellVolume:0,delta:0};bar._levels.set(tick,level);}
  if(signed>0)level.buyVolume+=t.size;else level.sellVolume+=t.size;
  level.delta+=signed;
 }
 flush();
 return out;
}
function validateBars(bars,now=Date.now()){
 if(!Array.isArray(bars)||!bars.length)return "NO_DELTA_BARS";
 let prev=-Infinity;
 for(const b of bars){
  if(b?.sourceQuality!==QUALITY||!b.venue||!b.symbol||!b.sessionId||
     b.closed!==true||!Number.isSafeInteger(b.openTime)||!Number.isSafeInteger(b.closeTime)||
     !Number.isSafeInteger(b.barMs)||b.closeTime!==b.openTime+b.barMs||
     b.closeTime>now||b.openTime<=prev||
     ![b.open,b.high,b.low,b.close,b.volume,b.buyVolume,b.sellVolume,b.delta,
       b.maxIntrabarDelta,b.minIntrabarDelta].every(finite)||
     b.volume<=0||b.high<Math.max(b.open,b.close)||b.low>Math.min(b.open,b.close)||
     Math.abs(b.delta-(b.buyVolume-b.sellVolume))>1e-6||
     Math.abs(b.volume-(b.buyVolume+b.sellVolume))>1e-6||
     b.maxIntrabarDelta<Math.max(0,b.delta)-1e-8||
     b.minIntrabarDelta>Math.min(0,b.delta)+1e-8)
    return "UNVERIFIED_OR_MALFORMED_DELTA_BAR";
  prev=b.openTime;
 }
 return null;
}
function contiguous(xs){
 return xs.length>0&&xs.every((b,i)=>i===0||
  (b.openTime===xs[i-1].closeTime&&b.sessionId===xs[i-1].sessionId&&
   b.symbol===xs[i-1].symbol&&b.venue===xs[i-1].venue&&b.barMs===xs[i-1].barMs));
}
function candidate(id,side,bars,detail){return {id,side,source:"ORDERFLOWS_DELTA_COURSE",
  evidenceBarTimes:bars.map(b=>b.openTime),detail,executionEnabled:false,
  edgeVerified:false,kind:"RESEARCH_HYPOTHESIS"};}
function detectSurge(bars){
 const x=bars.slice(-4);if(x.length!==4||!contiguous(x))return [];
 const [a,b,c,d]=x.map(y=>y.delta);
 if(a<0&&b>0&&c>b&&d>c)return [candidate("delta_surge","LONG",x,{pattern:"negative_then_three_increasing_positive_deltas",variant:"FOUR_BAR_VISUAL_EXAMPLE_NOT_UNIVERSAL_REQUIREMENT"})];
 if(a>0&&b<0&&c<b&&d<c)return [candidate("delta_surge","SHORT",x,{pattern:"positive_then_three_decreasing_negative_deltas",variant:"FOUR_BAR_VISUAL_EXAMPLE_NOT_UNIVERSAL_REQUIREMENT"})];
 return [];
}
function detectDivergence(bars,{swingLookback,equalTolerance}={}){
 if(!Number.isInteger(swingLookback)||swingLookback<2||!finite(equalTolerance)||equalTolerance<0)
  return {signals:[],blocked:"RESEARCH_SWING_LOOKBACK_AND_EQUAL_TOLERANCE_REQUIRED"};
 const x=bars.slice(-(swingLookback+1));
 if(x.length!==swingLookback+1||!contiguous(x))return {signals:[],blocked:null};
 const prior=x.slice(0,-1),last=x.at(-1);
 const high=Math.max(...prior.map(b=>b.high)),low=Math.min(...prior.map(b=>b.low));
 const signals=[];
 if(last.high>=high-equalTolerance&&last.delta<0)
  signals.push(candidate("delta_divergence","SHORT",[last],{referenceHigh:high,lookback:swingLookback,equalTolerance}));
 if(last.low<=low+equalTolerance&&last.delta>0)
  signals.push(candidate("delta_divergence","LONG",[last],{referenceLow:low,lookback:swingLookback,equalTolerance}));
 return {signals,blocked:null};
}
function closeNear(b,which,tolerance){
 const span=b.maxIntrabarDelta-b.minIntrabarDelta;
 if(!(span>0))return false;
 const target=which==="MAX"?b.maxIntrabarDelta:b.minIntrabarDelta;
 return Math.abs(b.delta-target)<=span*tolerance+1e-8;
}
function detectFlips(bars,{nearExtremeTolerance,allowOneInterveningBar=false}={}){
 if(!finite(nearExtremeTolerance)||nearExtremeTolerance<0||nearExtremeTolerance>1)
  return {signals:[],blocked:"RESEARCH_NEAR_EXTREME_TOLERANCE_REQUIRED"};
 if(typeof allowOneInterveningBar!=="boolean")return {signals:[],blocked:"INVALID_GAP_OPTION"};
 const last=bars.at(-1);if(!last)return {signals:[],blocked:null};
 const offsets=allowOneInterveningBar?[1,2]:[1];
 const signals=[];
 for(const distance of offsets){
  const first=bars.at(-1-distance);
  if(!first||!contiguous(bars.slice(-1-distance)))continue;
  if(nearZero(first.maxIntrabarDelta)&&closeNear(first,"MIN",nearExtremeTolerance)&&
     nearZero(last.minIntrabarDelta)&&closeNear(last,"MAX",nearExtremeTolerance))
   signals.push(candidate("delta_flips","LONG",[first,last],{interveningBars:distance-1,nearExtremeTolerance}));
  if(nearZero(first.minIntrabarDelta)&&closeNear(first,"MAX",nearExtremeTolerance)&&
     nearZero(last.maxIntrabarDelta)&&closeNear(last,"MIN",nearExtremeTolerance))
   signals.push(candidate("delta_flips","SHORT",[first,last],{interveningBars:distance-1,nearExtremeTolerance}));
 }
 return {signals,blocked:null};
}

// Lesson 3 ~26:37: session CVD/volume near zero (balance) followed by strong
// directional Delta. The instructor gives NO numerical cutoffs. Research only.
function detectCvdVolumeBalanceBreak(bars,{nearZeroRatioTolerance,strongDeltaThreshold}={}){
 if(!finite(nearZeroRatioTolerance)||nearZeroRatioTolerance<0||nearZeroRatioTolerance>1||
    !finite(strongDeltaThreshold)||strongDeltaThreshold<=0)
  return {signals:[],blocked:"RESEARCH_CVD_VOLUME_BALANCE_AND_STRONG_DELTA_THRESHOLDS_REQUIRED"};
 const x=bars.slice(-2);
 if(x.length!==2||!contiguous(x)||!x.every(b=>finite(b.cvdOverVolume)))
  return {signals:[],blocked:null};
 const [prior,last]=x;
 if(Math.abs(prior.cvdOverVolume)>nearZeroRatioTolerance||
    Math.abs(last.delta)<strongDeltaThreshold)return {signals:[],blocked:null};
 return {signals:[candidate("cvd_volume_balance_break",last.delta>0?"LONG":"SHORT",x,
  {nearZeroRatioTolerance,strongDeltaThreshold,sourceNote:"LESSON_3_26M37S"})],blocked:null};
}

/** Evaluate only research signals; never submit MT5 orders. */
function evaluate(bars,params={},now=Date.now()){
 const error=validateBars(bars,now);
 if(error)return {status:"DATA_BLOCKED",reason:error,signals:[],executionEnabled:false};
 const divergence=detectDivergence(bars,params),flips=detectFlips(bars,params),
  cvdBalance=detectCvdVolumeBalanceBreak(bars,params);
 return {status:"RESEARCH_ONLY",signals:[...detectSurge(bars),...divergence.signals,...flips.signals,...cvdBalance.signals],
  blockedParameters:[divergence.blocked,flips.blocked,cvdBalance.blocked].filter(Boolean),
  unimplementedFromVideo:["delta_transition","delta_tails","delta_bulges","delta_reversal"],
  executionEnabled:false};
}
module.exports={QUALITY,buildBars,validateBars,detectSurge,detectDivergence,detectFlips,detectCvdVolumeBalanceBreak,evaluate};