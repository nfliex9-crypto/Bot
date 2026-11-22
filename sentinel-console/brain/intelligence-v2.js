"use strict";
/**
 * Sentinel Adaptive Intelligence V2 (research-only decision layer).
 * Source-aware, causal, explainable. Makes no orders, changes no live config.
 * M15/H1 OHLC is NEVER treated as Footprint/Delta/DOM; verified trade tape
 * is a separate evidence class. Score is a heuristic, NOT a win probability.
 * Transaction costs are NOT modeled or deducted in the requested research.
 */
const VERSION="sentinel-adaptive-intelligence-v2.0";
const PERIOD={M15:900000,H1:3600000};
const SOURCE={
 pdf_sweep_bos:"OWNER_PDF_PRICE_PATTERN",
 pdf_fvg_retest:"OWNER_PDF_PRICE_PATTERN",
 sweep_divergence_bos:"COMPOSITE_RESEARCH_HYPOTHESIS",
 trend_delta_surge:"COMPOSITE_RESEARCH_HYPOTHESIS"
};
const PDF_NAME=Object.freeze({
 pdf_sweep_bos:"Market_Structure_And_Powerful_Setups_By_Wade_Fx_Setups1_1.pdf",
 pdf_fvg_retest:"9. Price_Action_Imbalance.pdf"
});
const num=x=>typeof x==="number"&&Number.isFinite(x);
const clamp=(x,lo=0,hi=1)=>Math.max(lo,Math.min(hi,x));
const round=(x,p=4)=>Number(x.toFixed(p));
function parseTime(x){const t=typeof x==="number"?x:Date.parse(x);return Number.isSafeInteger(t)?t:NaN}
function validateClosed(bars,period,now,min){
 if(!Array.isArray(bars)||bars.length<min)return {ok:false,reason:"INSUFFICIENT_CLOSED_BARS"};
 let prev=-Infinity;
 for(const x of bars){
  if(!x||![x.time,x.open,x.high,x.low,x.close].every(num)||
     !Number.isSafeInteger(x.time)||x.time<=prev||x.time+period>now||
     x.low<=0||x.high<Math.max(x.open,x.close)||x.low>Math.min(x.open,x.close))
   return {ok:false,reason:"UNVERIFIED_OR_UNCLOSED_OHLC"};
  prev=x.time;
 }
 const tail=bars.slice(-60);
 for(let i=1;i<tail.length;i++)if(tail[i].time-tail[i-1].time!==period)
  return {ok:false,reason:"MISSING_MARKET_BARS"};
 return {ok:true};
}
function ema(values,n){
 if(values.length<n)return null;
 let v=values.slice(0,n).reduce((a,b)=>a+b,0)/n;const w=2/(n+1);
 for(const x of values.slice(n))v+=(x-v)*w;
 return v;
}
function atr(bars,n=14){
 if(bars.length<n+1)return null;
 let sum=0;
 for(let i=bars.length-n;i<bars.length;i++){
  const x=bars[i],p=bars[i-1];
  sum+=Math.max(x.high-x.low,Math.abs(x.high-p.close),Math.abs(x.low-p.close));
 }
 return sum/n;
}
function marketFeatures({m15,h1,now}){
 const m=validateClosed(m15,PERIOD.M15,now,65);
 if(!m.ok)return {ready:false,reason:"M15_"+m.reason};
 const h=validateClosed(h1,PERIOD.H1,now,65);
 if(!h.ok)return {ready:false,reason:"H1_"+h.reason};
 const last=m15.at(-1),hour=h1.at(-1),a=atr(m15),ha=atr(h1),closes=h1.map(b=>b.close);
 if(!(a>0)||!(ha>0))return {ready:false,reason:"VOLATILITY_UNAVAILABLE"};
 const trend=(ema(closes,20)-ema(closes,50))/ha;
 const range=Math.max(last.high-last.low,1e-12),closeLoc=clamp((last.close-last.low)/range);
 const prev=m15.slice(-17,-1),hi=Math.max(...prev.map(b=>b.high)),lo=Math.min(...prev.map(b=>b.low));
 const shortAtr=atr(m15,7),longAtr=atr(m15,42);
 const ratio=shortAtr/longAtr;
 const regime=ratio>1.65?"VOLATILE":ratio<0.65?"CONTRACTING":Math.abs(trend)>0.65?"TRENDING":"RANGING";
 const freshness=Math.max(0,now-(last.time+PERIOD.M15));
 const hFreshness=Math.max(0,now-(hour.time+PERIOD.H1));
 if(freshness>PERIOD.M15||hFreshness>4*PERIOD.H1)
  return {ready:false,reason:"STALE_BROKER_BARS"};
 return {ready:true,source:"CLOSED_BROKER_OHLC",lastTime:last.time,
  trendATR:round(trend),bodyATR:round((last.close-last.open)/a),closeLocation:round(closeLoc),
  rangeBreak:last.close>hi?"UP":last.close<lo?"DOWN":"NONE",
  volatilityRatio:round(ratio),regime,atr:round(a,8),h1Atr:round(ha,8),
  lastClose:last.close};
}
/** Executed-tape confirmation must match SAME venue AND symbol and closed bar.
 * Never mix Binance BTCUSDT into Fusion MT5 BTCUSD or XAUUSD research.
 */
function verifiedTape(tape,{symbol,venue,barTime,closeTime}){
 if(!tape)return {status:"NOT_PROVIDED",weight:0};
 if(tape.sourceQuality!=="VERIFIED_AGGRESSOR_TRADES"||tape.closed!==true||
    !num(tape.delta)||!num(tape.volume)||!(tape.volume>0)||
    tape.symbol!==symbol||tape.venue!==venue||tape.openTime!==barTime||
    tape.closeTime!==closeTime)
   return {status:"REJECTED_MISMATCHED_OR_SYNTHETIC",weight:0};
 return {status:"VERIFIED_EXECUTED_TRADE_TAPE",weight:round(clamp(Math.abs(tape.delta)/tape.volume)),
  deltaSide:tape.delta>0?1:tape.delta<0?-1:0};
}
function evaluateCandidate({signal,features,orderflow=null,venue=null}){
 if(!features?.ready)return {status:"BLOCKED_DATA",reason:features?.reason||"MARKET_UNAVAILABLE"};
 if(!signal||![-1,1].includes(signal.side)||!Number.isSafeInteger(signal.bar_time)||
    features.lastTime!==signal.bar_time||!SOURCE[signal.family])
  return {status:"BLOCKED_SOURCE",reason:"UNVERIFIED_SOURCE_OR_BAR"};
 const source=SOURCE[signal.family];
 if(source==="OWNER_PDF_PRICE_PATTERN"&&(
    signal.source_kind!=="OWNER_PDF_PRICE_PATTERN"||
    signal.source_pdf!==PDF_NAME[signal.family]||
    !Array.isArray(signal.source_pages)||!signal.source_pages.length||
    !signal.source_pages.every(n=>Number.isSafeInteger(n)&&n>0)))
  return {status:"BLOCKED_SOURCE",reason:"PDF_PAGE_PROVENANCE_MISSING"};
 if(source==="COMPOSITE_RESEARCH_HYPOTHESIS"&&signal.kind!==source)
  return {status:"BLOCKED_SOURCE",reason:"RESEARCH_ORIGIN_MISMATCH"};
 const trend=clamp(signal.side*features.trendATR/1.3),body=clamp(signal.side*features.bodyATR),
  close=signal.side===1?features.closeLocation:1-features.closeLocation,
  structure=features.rangeBreak===(signal.side===1?"UP":"DOWN")?1:0.3;
 const vol=features.regime==="VOLATILE"?0.35:features.regime==="CONTRACTING"?0.55:0.8;
 const quality=round(clamp(trend*.28+body*.24+close*.2+structure*.2+vol*.08));
 const tape=verifiedTape(orderflow,{symbol:signal.symbol,venue,
  barTime:signal.bar_time,closeTime:signal.bar_time+PERIOD.M15});
 const agreement=tape.status==="VERIFIED_EXECUTED_TRADE_TAPE"&&tape.deltaSide===signal.side;
 // Tape remains independent diagnostic; cannot approve unverified strategy.
 return {status:"RESEARCH_CANDIDATE",family:signal.family,symbol:signal.symbol,
  side:signal.side===1?"LONG":"SHORT",signalTime:signal.bar_time,
  score:quality,scoreMeaning:"HEURISTIC_SETUP_QUALITY_NOT_WIN_PROBABILITY",
  regime:features.regime,source,orderflow:{...tape,agreesWithSide:agreement},
  factors:{trend:round(trend),body:round(body),close:round(close),structure,volatility:vol},
  action:"ANALYZE_ONLY",orderExecutionAllowed:false};
}
function rank({m15,h1,signals=[],now=Date.now(),venue=null,orderflow=null}={}){
 if(!Number.isSafeInteger(now))throw Error("INVALID_REFERENCE_TIME");
 const features=marketFeatures({m15,h1,now});
 if(!Array.isArray(signals))throw Error("SIGNALS_EXPECTED");
 const candidates=signals.map(signal=>evaluateCandidate({signal,features,venue,orderflow}));
 const qualified=candidates.filter(x=>x.status==="RESEARCH_CANDIDATE")
  .sort((a,b)=>b.score-a.score||a.family.localeCompare(b.family));
 return {version:VERSION,ready:features.ready,reason:features.reason||null,
  scoreBasis:"GROSS_PRICE_ONLY_NO_TRANSACTION_COSTS",featureSource:"CLOSED_BROKER_OHLC",
  features,candidates,ranked:qualified,executionEnabled:false,
  decision:"RESEARCH_ONLY_NO_ORDERS"};
}
/** Forward evidence from completed PRE-TAGGED demo fills, chronological
 * untouched OOS. Evidence can NOT create an order authorization.
 */
function forwardEvidence(rows,{minTrain=20,minOos=15,minOosDays=5,asOf=Date.now()}={}){
 if(!Array.isArray(rows))throw Error("BROKER_TRADES_EXPECTED");
 if(!Number.isSafeInteger(asOf))throw Error("INVALID_EVIDENCE_CUTOFF");
 const groups=new Map(),used=new Set();let rejected=0;
 for(const r of rows){
  const open=parseTime(r?.openTime),close=parseTime(r?.closeTime),tag=parseTime(r?.taggedAt);
  const identity=[r?.accountId,r?.ticket].join("|");
  if(r?.isDemo!==true||r?.brokerVerified!==true||r?.complete!==true||
     r?.partial===true||!r?.ticket||!r?.accountId||!r?.symbol||!SOURCE[r?.family]||
     !num(r?.grossProfit)||!num(r?.riskAtEntry)||!(r.riskAtEntry>0)||
     !Number.isFinite(open)||!Number.isFinite(close)||!Number.isFinite(tag)||
     !(tag<=open&&open<close&&close<=asOf)||used.has(identity)||
     !Number.isFinite(r.grossProfit/r.riskAtEntry)){rejected++;continue}
  used.add(identity);
  const key=r.symbol+"|"+r.family,arr=groups.get(key)||[];
  arr.push({time:close,grossR:r.grossProfit/r.riskAtEntry,ticket:String(r.ticket)});
  groups.set(key,arr);
 }
 const strategies=[];
 for(const [key,arr] of groups){
  arr.sort((a,b)=>a.time-b.time||a.ticket.localeCompare(b.ticket));
  const split=Math.max(1,Math.floor(arr.length*.65)),train=arr.slice(0,split),oos=arr.slice(split);
  const measures=x=>{
   const r=x.map(t=>t.grossR),wins=r.filter(v=>v>0),losses=r.filter(v=>v<0);
   const sum=r.reduce((a,b)=>a+b,0),gain=wins.reduce((a,b)=>a+b,0),loss=-losses.reduce((a,b)=>a+b,0);
   return {trades:r.length,winPct:r.length?round(wins.length/r.length*100,2):null,
    expectancyR:r.length?round(sum/r.length):null,profitFactor:loss?round(gain/loss):null,
    grossTotalR:round(sum),days:new Set(x.map(v=>new Date(v.time).toISOString().slice(0,10))).size};
  };
  const tr=measures(train),os=measures(oos);
  const enough=tr.trades>=minTrain&&os.trades>=minOos&&os.days>=minOosDays;
  const status=!enough?"COLLECTING_FORWARD":os.expectancyR>0&&tr.expectancyR>0?
    "PROMISING_REQUIRES_INDEPENDENT_REVIEW":"WEAK_OR_UNSTABLE";
  const [symbol,family]=key.split("|");
  strategies.push({symbol,family,status,train:tr,oos:os,executionApproved:false,
   promotedToDemo:false,explanation:enough?"Chronological gross forward review":"Insufficient labeled days or completed trades"});
 }
 strategies.sort((a,b)=>a.symbol.localeCompare(b.symbol)||a.family.localeCompare(b.family));
 return {version:VERSION,records:rows.length,accepted:used.size,rejected,strategies,
  split:"CHRONOLOGICAL_65_35",costDeductions:0,ordersEnabled:false};
}
module.exports={VERSION,PERIOD,SOURCE,PDF_NAME,validateClosed,marketFeatures,verifiedTape,
 evaluateCandidate,rank,forwardEvidence};
