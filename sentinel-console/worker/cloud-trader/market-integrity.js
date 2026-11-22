"use strict";
/**
 * Sentinel V2 broker OHLC integrity audit. Research / telemetry only.
 * Cross-checks closed M15 and H1 candles from the SAME broker account.
 * Does not fabricate missing candles, market sessions, Delta or prices.
 * Exact session gaps remain unknown unless the broker supplies a calendar.
 */
const PERIOD=Object.freeze({M15:900000,H1:3600000});
const finite=x=>typeof x==="number"&&Number.isFinite(x);
function check(bars,period,now,min){
 if(!Array.isArray(bars)||bars.length<min)return {ok:false,reason:"INSUFFICIENT_BROKER_BARS"};
 let previous=-Infinity;
 for(const b of bars){
  if(!b||!Number.isSafeInteger(b.time)||b.time<=previous||
     b.time%period!==0||b.time+period>now||
     ![b.open,b.high,b.low,b.close].every(finite)||
     b.low<=0||b.high<Math.max(b.open,b.close)||b.low>Math.min(b.open,b.close))
   return {ok:false,reason:"INVALID_OR_UNCLOSED_BROKER_BAR"};
  previous=b.time;
 }
 const window=bars.slice(-Math.min(bars.length,period===PERIOD.M15?32:16));
 let gaps=0,missingSlots=0;
 for(let i=1;i<window.length;i++){
  const diff=window[i].time-window[i-1].time;
  if(diff!==period){gaps++;missingSlots+=Math.max(0,Math.floor(diff/period)-1);}
 }
 return {ok:true,reason:"BARS_VALID",gaps,missingSlots,lastTime:bars.at(-1).time,
  lastCloseAt:bars.at(-1).time+period};
}
function audit({m15,h1,now=Date.now(),brokerTickSize,symbol=null,venue=null}={}){
 const base={source:"SAME_BROKER_CLOSED_OHLC",symbol,venue,executionEnabled:false};
 if(!Number.isSafeInteger(now))return {...base,ok:false,reason:"INVALID_REFERENCE_TIME"};
 const m=check(m15,PERIOD.M15,now,65),h=check(h1,PERIOD.H1,now,60);
 if(!m.ok)return {...base,ok:false,reason:"M15_"+m.reason};
 if(!h.ok)return {...base,ok:false,reason:"H1_"+h.reason};
 const gaps={m15:m.gaps,h1:h.gaps,missingM15:m.missingSlots,missingH1:h.missingSlots};
 if(m.gaps||h.gaps)return {...base,ok:false,reason:"RECENT_BAR_GAPS_UNCLASSIFIED",gaps};
 if(now-m.lastCloseAt>PERIOD.M15||now-h.lastCloseAt>4*PERIOD.H1)
  return {...base,ok:false,reason:"STALE_BROKER_FEED",gaps};
 if(!finite(brokerTickSize)||brokerTickSize<=0)
  return {...base,ok:false,reason:"BROKER_TICK_SIZE_UNVERIFIED",gaps};
 const byTime=new Map(m15.map(b=>[b.time,b]));
 let checked=0,maxTickError=0;
 for(const hour of h1.slice(-Math.min(h1.length,24))){
  const sub=[0,1,2,3].map(i=>byTime.get(hour.time+i*PERIOD.M15));
  if(sub.some(x=>!x))continue; // Incomplete H1 coverage is not evidence.
  const rebuilt={open:sub[0].open,close:sub[3].close,
   high:Math.max(...sub.map(x=>x.high)),low:Math.min(...sub.map(x=>x.low))};
  for(const field of ["open","high","low","close"]){
   const error=Math.abs(rebuilt[field]-hour[field])/brokerTickSize;
   if(!Number.isFinite(error))return {...base,ok:false,reason:"CROSS_TIMEFRAME_NUMERIC_ERROR",gaps};
   maxTickError=Math.max(maxTickError,error);
   if(error>2.000001)return {...base,ok:false,reason:"M15_H1_BROKER_PRICE_MISMATCH",
    gaps,comparedH1:checked+1,field,mismatchHour:hour.time,
    tickError:Number(error.toFixed(4))};
  }
  checked++;
 }
 if(checked<2)return {...base,ok:false,reason:"CROSS_TIMEFRAME_OVERLAP_INSUFFICIENT",
  gaps,comparedH1:checked};
 return {...base,ok:true,reason:"BROKER_M15_H1_CONSISTENT",gaps,
  comparedH1:checked,maxTickError:Number(maxTickError.toFixed(4)),
  lastM15CloseAt:m.lastCloseAt,lastH1CloseAt:h.lastCloseAt,
  evidence:"SAME_BROKER_OHLC_CROSSCHECK_NOT_EXECUTED_ORDERFLOW"};
}
module.exports={PERIOD,check,audit};
