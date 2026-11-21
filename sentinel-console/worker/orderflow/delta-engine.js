"use strict";
/**
 * Orderflows Delta Course: deterministic research-only tape aggregation.
 *
 * No OHLC/tick_volume substitution. The caller must provide executed trades
 * in temporal order, with venue, instrument, session, side, size and price.
 * Source declaration is NOT independent verification of market-data truth.
 * NO broker execution API or order placement is present in this module.
 */
const curriculum=require("../../brain/orderflows-delta-curriculum.js");
const finite=x=>typeof x==="number"&&Number.isFinite(x);
const BASE={research_only:true,execution_enabled:false,edge_verified:false,auto_promotion:false,
 source_course:"OWNER_DELTA_VIDEO_COURSE",review_status:"VISUAL_SLIDE_RULE_NOT_AUDIO_TRANSCRIBED"};
function validConfig(config){
 const barMs=config?.barMs,tickSize=config?.tickSize,now=config?.now;
 if(!Number.isSafeInteger(barMs)||barMs<1000||barMs>86400000||
    !finite(tickSize)||tickSize<=0||!Number.isSafeInteger(now))
   throw Error("INVALID_DELTA_AGGREGATION_CONFIG");
 const contract=config?.contract;
 if(contract?.source!=="EXECUTED_TAPE"||
    !["EXCHANGE_AGGRESSOR_FLAG","ESTIMATED_SIDE"].includes(contract.aggressorMethod)||
    !/^[A-Za-z0-9._-]{2,60}$/.test(contract.venue||"")||
    !/^[A-Za-z0-9._#-]{2,60}$/.test(contract.symbol||""))
   throw Error("EXECUTED_TAPE_PROVENANCE_REQUIRED");
 return contract;
}
function bucket(price,tickSize){
 const idx=Math.round(price/tickSize);
 if(!Number.isSafeInteger(idx)||Math.abs(idx*tickSize-price)>tickSize*1e-6)
  throw Error("TRADE_PRICE_NOT_ALIGNED_TO_TICK");
 return idx;
}
function aggregateTrades(trades,config){
 const contract=validConfig(config);
 if(!Array.isArray(trades)||trades.length>500000)throw Error("INVALID_TAPE_LENGTH");
 const {barMs,tickSize,now}=config;
 const byBar=[],keySet=new Set();let lastT=-Infinity,lastSeq=-Infinity;
 let session=null,cvd=0,sessionVolume=0,current=null;
 const claimedExchangeFlag=contract.aggressorMethod==="EXCHANGE_AGGRESSOR_FLAG";
 for(const t of trades){
  const at=t?.time,seq=t?.sequence,size=t?.size,price=t?.price,side=t?.side;
  if(!Number.isSafeInteger(at)||at<0||!Number.isSafeInteger(seq)||seq<0||
     (at<lastT)||(at===lastT&&seq<=lastSeq)||
     !finite(size)||size<=0||!finite(price)||price<=0||
     !["BUY","SELL"].includes(side)||typeof t.sessionId!=="string"||
     t.sessionId.length<1||t.sessionId.length>100||
     t.symbol!==contract.symbol||t.venue!==contract.venue)
    throw Error("INVALID_NONMONOTONIC_OR_MIXED_TAPE");
  lastT=at;lastSeq=seq;
  const id=t.venue+"|"+t.symbol+"|"+seq;
  if(keySet.has(id))throw Error("DUPLICATE_TRADE_SEQUENCE");
  keySet.add(id);
  const p=bucket(price,tickSize),start=Math.floor(at/barMs)*barMs;
  if(session!==t.sessionId){session=t.sessionId;cvd=0;sessionVolume=0;}
  if(current&&(current.start!==start||current.session_id!==session)){
   if(current.start===start)throw Error("SESSION_RESET_INSIDE_BAR_REQUIRES_SPLIT");
   byBar.push(current);current=null;
  }
  if(!current){
   current={start,end:start+barMs,session_id:session,symbol:t.symbol,venue:t.venue,
    o:price,h:price,l:price,c:price,executed_volume:0,buy_volume:0,sell_volume:0,
    delta:0,max_delta:0,min_delta:0,cvd:0,cvd_over_volume:0,
    footprint:[],source_quality:claimedExchangeFlag?"DECLARED_EXCHANGE_SIDE":"ESTIMATED_SIDE",
    execution_enabled:false};
   current._levels=new Map();
  }
  current.h=Math.max(current.h,price);current.l=Math.min(current.l,price);current.c=price;
  current.executed_volume+=size;sessionVolume+=size;
  if(side==="BUY")current.buy_volume+=size;else current.sell_volume+=size;
  const signed=side==="BUY"?size:-size;cvd+=signed;current.delta+=signed;
  current.max_delta=Math.max(current.max_delta,current.delta);
  current.min_delta=Math.min(current.min_delta,current.delta);
  current.cvd=cvd;current.cvd_over_volume=sessionVolume>0?cvd/sessionVolume:0;
  let level=current._levels.get(p);
  if(!level){level={price:p*tickSize,buy_volume:0,sell_volume:0};current._levels.set(p,level);}
  if(side==="BUY")level.buy_volume+=size;else level.sell_volume+=size;
 }
 if(current)byBar.push(current);
 const completed=[],incomplete=[];
 for(const b of byBar){
  b.footprint=Array.from(b._levels.values()).sort((x,y)=>x.price-y.price);
  delete b._levels;
  b.footprint.forEach(p=>{p.delta=p.buy_volume-p.sell_volume;});
  // Research-derived convention, NOT a lesson-specific trade-entry rule:
  // buy at level i minus sell at the immediately lower price level.
  const prices=new Map(b.footprint.map(p=>[bucket(p.price,tickSize),p]));
  b.diagonal_footprint=b.footprint.map(p=>{
   const below=prices.get(bucket(p.price,tickSize)-1);
   return {price:p.price,buy_minus_lower_sell:
    below?p.buy_volume-below.sell_volume:null,
    method:"RESEARCH_DERIVED_ADJACENT_PRICE_COMPARISON"};
  });
  if(Math.abs(b.buy_volume-b.sell_volume-b.delta)>Math.max(1,b.executed_volume)*1e-9)
   throw Error("DELTA_VOLUME_RECONCILIATION_FAILED");
  if(b.end<=now)completed.push(b);else incomplete.push(b);
 }
 return {...BASE,status:"RESEARCH_TAPE_AGGREGATED",
  provenance:{venue:contract.venue,symbol:contract.symbol,
    aggressor_method:contract.aggressorMethod,
    independently_verified:false,source_is_broker_cfd:false},
  closed_bars:completed,excluded_open_bars:incomplete.length,
  input_trades:trades.length,
  execution_block_reason:claimedExchangeFlag?"NOT_BACKTESTED_OR_APPROVED":"ESTIMATED_AGGRESSOR_SIDE"};
}
function evt(id,side,bars,extra={}){
 return {...BASE,id,side,bar_start:bars.at(-1).start,
  source_ref:id==="delta_surge"?"delta_l4a:09:00":"delta_l4b:"+(
   id==="delta_divergence"?"01:30":"06:30"),
  research_assumptions:[],...extra};
}
function scan(bars,{comparisonWindow=null,equalToleranceTicks=null,
 nearExtremeFraction=null,allowInterveningFlip=false,tickSize=null}={}){
 if(!Array.isArray(bars))throw Error("DELTA_BARS_REQUIRED");
 for(let i=0;i<bars.length;i++){
  const b=bars[i];
  if(!Number.isSafeInteger(b?.start)||!Number.isSafeInteger(b?.end)||
     b.end<=b.start||!finite(b.delta)||!finite(b.max_delta)||!finite(b.min_delta)||
     !finite(b.h)||!finite(b.l)||b.l>b.h||b.max_delta<b.delta-1e-7||
     b.min_delta>b.delta+1e-7||b.max_delta<0||b.min_delta>0||
     i>0&&bars[i-1].start>=b.start)
     throw Error("INVALID_DELTA_BARS");
 }
 const ev=[],pending=[];
 if(bars.length<2)return {...BASE,status:"INSUFFICIENT_BARS",events:ev,pending_configuration:pending};
 const sameStream=xs=>xs.every((b,i)=>i===0||(
  b.venue===xs[0].venue&&b.symbol===xs[0].symbol&&
  b.session_id===xs[0].session_id&&b.start===xs[i-1].end));
 for(let i=3;i<bars.length;i++){
  const four=bars.slice(i-3,i+1);
  if(!sameStream(four))continue;
  const [a,b,c,d]=four.map(x=>x.delta);
  if(a<0&&b>0&&c>b&&d>c)ev.push(evt("delta_surge","LONG",four,
    {rule:"FOUR_FINAL_DELTAS_NEG_POS_INCREASING",
      research_assumptions:["CONTIGUOUS_SAME_SESSION_BARS"]}));
  if(a>0&&b<0&&c<b&&d<c)ev.push(evt("delta_surge","SHORT",four,
    {rule:"FOUR_FINAL_DELTAS_POS_NEG_DECREASING",
      research_assumptions:["CONTIGUOUS_SAME_SESSION_BARS"]}));
 }
 if(comparisonWindow===null||equalToleranceTicks===null||tickSize===null){
  pending.push("DIVERGENCE_PIVOT_WINDOW_EQUAL_TOLERANCE_AND_TICK_SIZE_UNSPECIFIED_BY_COURSE");
 }else{
  if(!Number.isInteger(comparisonWindow)||comparisonWindow<1||comparisonWindow>500||
     !Number.isInteger(equalToleranceTicks)||equalToleranceTicks<0||equalToleranceTicks>50||
     !finite(tickSize)||tickSize<=0)throw Error("INVALID_DIVERGENCE_RESEARCH_CONFIG");
  for(let i=comparisonWindow;i<bars.length;i++){
   const cur=bars[i],prior=bars.slice(i-comparisonWindow,i);
   if(prior.some(x=>x.session_id!==cur.session_id||x.symbol!==cur.symbol||x.venue!==cur.venue))continue;
   const priorH=Math.max(...prior.map(x=>x.h)),priorL=Math.min(...prior.map(x=>x.l));
   const eps=equalToleranceTicks*tickSize;
   if(cur.h>=priorH-eps&&cur.delta<0)ev.push(evt("delta_divergence","SHORT",[cur],
    {reference_high:priorH,rule:"EQUAL_OR_NEW_HIGH_WITH_NEGATIVE_FINAL_DELTA",
     research_assumptions:["PIVOT_WINDOW_"+comparisonWindow,"EQUALITY_TICKS_"+equalToleranceTicks]}));
   if(cur.l<=priorL+eps&&cur.delta>0)ev.push(evt("delta_divergence","LONG",[cur],
    {reference_low:priorL,rule:"EQUAL_OR_NEW_LOW_WITH_POSITIVE_FINAL_DELTA",
     research_assumptions:["PIVOT_WINDOW_"+comparisonWindow,"EQUALITY_TICKS_"+equalToleranceTicks]}));
  }
 }
 if(nearExtremeFraction===null){
  pending.push("FLIP_NEAR_MAX_MIN_NUMERICAL_TOLERANCE_UNSPECIFIED_BY_COURSE");
 }else{
  if(!finite(nearExtremeFraction)||nearExtremeFraction<0||nearExtremeFraction>0.5)
   throw Error("INVALID_FLIP_TOLERANCE");
  const near=(v,ext,b)=>Math.abs(v-ext)<=nearExtremeFraction*(b.max_delta-b.min_delta)+1e-9;
  const zero=v=>Math.abs(v)<1e-9;
  for(let i=1;i<bars.length;i++){
   const gaps=allowInterveningFlip?[0,1]:[0];
   for(const gap of gaps){
    const j=i-1-gap;
    if(j<0)continue;
    const a=bars[j],b=bars[i];
    if(a.symbol!==b.symbol||a.venue!==b.venue||a.session_id!==b.session_id||
       b.start-a.end!==gap*(b.end-b.start))continue;
    const between=gap?bars[i-1]:null;
    if(between&&(between.start!==a.end||between.end!==b.start||
       between.session_id!==a.session_id))continue;
    if(zero(a.max_delta)&&near(a.delta,a.min_delta,a)&&
       zero(b.min_delta)&&near(b.delta,b.max_delta,b))
     ev.push(evt("delta_flips","LONG",[a,b],
       {first_bar_start:a.start,gap_bars:gap,rule:"ZERO_MAX_NEAR_MIN_TO_ZERO_MIN_NEAR_MAX",
        research_assumptions:["NEAR_EXTREME_FRACTION_"+nearExtremeFraction]}));
    if(zero(a.min_delta)&&near(a.delta,a.max_delta,a)&&
       zero(b.max_delta)&&near(b.delta,b.min_delta,b))
     ev.push(evt("delta_flips","SHORT",[a,b],
       {first_bar_start:a.start,gap_bars:gap,rule:"ZERO_MIN_NEAR_MAX_TO_ZERO_MAX_NEAR_MIN",
        research_assumptions:["NEAR_EXTREME_FRACTION_"+nearExtremeFraction]}));
   }
  }
 }
 return {...BASE,status:"RESEARCH_EVENTS_NOT_ORDERS",events:ev,
  pending_configuration:pending,setup_coverage:{executable_detectors:3,
   named_without_rules:curriculum.SETUPS.filter(s=>s.status==="NAMED_NOT_EXPLAINED").map(s=>s.id)},
  source_assessment:"VISUAL_SLIDES_ONLY_NOT_FULL_AUDIO_TRANSCRIPTION"};
}
module.exports={aggregateTrades,scan,validConfig};
