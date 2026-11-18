"use strict";
/* Strict research-only DEMO upload validator. The agent is authenticated by
 * the paired-device bridge; price history is still explicitly UNVERIFIED.
 */
const TF_SECONDS={M15:900,H1:3600};
function normalizeUpload(body,{now=Date.now(),maxBars=500}={}){
 if(body?.source!=="LOCAL_MT5_DEMO_TERMINAL"||body?.trade_mode!=="demo")
  throw Error("LOCAL_DEMO_SOURCE_REQUIRED");
 const symbol=String(body.symbol||"").trim(),timeframe=String(body.timeframe||"");
 if(!/^[A-Za-z0-9._#-]{2,24}$/.test(symbol)||!Object.hasOwn(TF_SECONDS,timeframe))
  throw Error("INVALID_SYMBOL_OR_TIMEFRAME");
 const rows=body.candles;
 if(!Array.isArray(rows)||!rows.length||rows.length>maxBars)
  throw Error("INVALID_UPLOAD_SIZE");
 const bars=[];
 const lower=Date.UTC(2010,0,1)/1000;
 for(const r of rows){
  const t=r?.timestamp;
  if(!Number.isSafeInteger(t)||t<lower||t+TF_SECONDS[timeframe]>now/1000)
   throw Error("UNCLOSED_OR_INVALID_BAR");
  const {open,high,low,close}=r;
  if([open,high,low,close].some(x=>typeof x!=="number"||!Number.isFinite(x)||x<=0)||
    high<Math.max(open,close,low)||low>Math.min(open,close,high))
   throw Error("INVALID_OHLC");
  if(r.spread!==null&&r.spread!==undefined&&
   (typeof r.spread!=="number"||!Number.isFinite(r.spread)||r.spread<0))
   throw Error("INVALID_SPREAD");
  if(!Number.isSafeInteger(r.tickVolume)||r.tickVolume<0)
   throw Error("INVALID_TICK_VOLUME");
  bars.push({time:new Date(t*1000).toISOString(),open,high,low,close,
   spread:r.spread>0?r.spread:null,tick_volume:r.tickVolume});
 }
 bars.sort((a,b)=>a.time.localeCompare(b.time));
 if(bars.some((x,i)=>i>0&&x.time===bars[i-1].time))
  throw Error("DUPLICATE_BAR");
 return {symbol,timeframe,bars,unverified:true,orders_enabled:false};
}
module.exports={normalizeUpload};
