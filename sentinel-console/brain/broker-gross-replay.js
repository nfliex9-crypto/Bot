"use strict";
/**
 * Sentinel V2: CAUSAL broker M15/H1 source-pattern replay, GROSS ONLY.
 *
 * Uses historical closed candles captured from the same broker/account.
 * No synthetic fee/spread, no simulated commissions, swaps or slippage.
 * No execution API, no order side effects, no automatic promotion.
 *
 * Signals are decided on a fully closed M15 candle with completed H1 bars.
 * Enter at NEXT M15 open only when candles are contiguous; stop-before-target
 * within an ambiguous intrabar collision; stops account for opening gaps.
 * Training trades whose exits cross the untouched OOS boundary are purged.
 * Historical bid/ask, tick-size, volume and account-specific constraints are
 * unavailable: all results are GROSS, price-only RESEARCH HYPOTHESES.
 */
const core=require("../worker/cloud-trader/core.js");
const TF15=900000,TF60=3600000;
function number(x){return typeof x==="number"&&Number.isFinite(x)}
function parseTime(x){const v=typeof x==="number"?x:Date.parse(String(x||""));return Number.isSafeInteger(v)?v:NaN}
function normalize(raw,tf,asOf=Date.now()){
 if(!Number.isSafeInteger(asOf))throw Error("INVALID_REPLAY_ASOF");
 if(!Array.isArray(raw))throw Error("REPLAY_BARS_REQUIRED");
 const out=[];let last=-Infinity;
 for(const b of raw){
  const time=parseTime(b.time??b.bar_time),open=Number(b.open),
    high=Number(b.high),low=Number(b.low),close=Number(b.close);
  if(!Number.isSafeInteger(time)||time<=last||![open,high,low,close].every(number)||
    !(low>0)||high<Math.max(open,close)||low>Math.min(open,close)||
    time%tf!==0)throw Error("REPLAY_INVALID_OR_UNSORTED_BROKER_BAR");
  if(time+tf>asOf)throw Error("REPLAY_UNCLOSED_OR_FUTURE_BAR");
  last=time;out.push({time,open,high,low,close});
 }
 return out;
}
function metrics(trades){
 const rs=trades.map(x=>x.grossR),n=rs.length;
 let gains=0,losses=0,total=0,peak=0,maxDD=0,equity=1,eqPeak=1,eqDD=0;
 const riskFraction=.0025;
 for(const r of rs){
  total+=r;if(r>0)gains+=r;else losses-=r;
  peak=Math.max(peak,total);maxDD=Math.max(maxDD,peak-total);
  equity*=Math.max(0,1+r*riskFraction);
  eqPeak=Math.max(eqPeak,equity);eqDD=Math.max(eqDD,1-equity/eqPeak);
 }
 const round=(v,n=4)=>Number(v.toFixed(n));
 return {trades:n,wins:rs.filter(x=>x>0).length,
  winRatePct:n?round(rs.filter(x=>x>0).length/n*100,2):null,
  expectancyGrossR:n?round(total/n):null,totalGrossR:round(total),
  profitFactor:losses?round(gains/losses):null,
  maxDrawdownGrossR:round(maxDD),hypotheticalEquityPct:round((equity-1)*100),
  hypotheticalMaxDrawdownPct:round(eqDD*100),
  activeDays:new Set(trades.map(x=>new Date(x.entryTime).toISOString().slice(0,10))).size};
}
function run({symbol,m15,h1,accountSource="FUSION_MT5_DEMO",
              holdBars=12,stopATR=null,targetR=null,splitFraction=.65,
              asOf=Date.now()}={}){
 if(!["XAUUSD","BTCUSD","NAS100","EURUSD"].includes(symbol))
  throw Error("REPLAY_SYMBOL_NOT_ALLOWED");
 if(!Number.isSafeInteger(holdBars)||holdBars<1||holdBars>48||
    !(splitFraction>.5&&splitFraction<.9)||
    (stopATR!==null&&!(number(stopATR)&&stopATR>0))||
    (targetR!==null&&!(number(targetR)&&targetR>0)))
  throw Error("REPLAY_INVALID_OPTIONS");
 const m=normalize(m15,TF15,asOf),h=normalize(h1,TF60,asOf);
 if(m.length<200||h.length<100)throw Error("INSUFFICIENT_MATCHED_BROKER_HISTORY");
 const boundaryIndex=Math.floor(m.length*splitFraction);
 const boundary=m[boundaryIndex].time;
 const dataset={symbol,venue:accountSource,barCountM15:m.length,barCountH1:h.length,
  trainThroughUtc:new Date(boundary).toISOString(),holdBars,
  assumptions:{costDeductions:0,spreadDeductions:0,commissionDeductions:0,
   slippageDeductions:0,swapDeductions:0,entry:"NEXT_CONTIGUOUS_M15_OPEN",
   exit:"STOP_FIRST_AMBIGUOUS_INTRABAR",
   model:"GROSS_PRICE_ONLY_NO_ACTUAL_BID_ASK",
   equityRiskPct:.25},
  executionEnabled:false};
 const trades=[],liveThrough=new Map();let hourIndex=0,skippedGaps=0;
 for(let i=110;i<m.length-1;i++){
  const t=m[i].time+TF15;
  if(m[i+1].time!==t){skippedGaps++;continue}
  while(hourIndex<h.length&&h[hourIndex].time+TF60<=t)hourIndex++;
  const hour=h.slice(0,hourIndex);
  if(hour.length<90)continue;
  // No future OHLC candle, no future H1 hour, and no bar from a later session.
  const context=m.slice(Math.max(0,i-175),i+1);
  if(context.length<110)continue;
  const signal=core.decide(symbol,context,hour,t,"source_only",{pdf_sweep_bos:1,pdf_fvg_retest:1});
  if(!signal)continue;
  const prevExit=liveThrough.get(signal.family)||-1;
  if(i<prevExit)continue;
  const entryBar=m[i+1],entry=entryBar.open,side=signal.side;
  const risk=signal.atr*(stopATR??signal.stop_atr),reward=targetR??signal.reward_r;
  if(!(risk>0&&reward>0))continue;
  const stop=entry-side*risk,target=entry+side*risk*reward;
  let exitAt=null,exit=null,reason=null,closedIndex=-1;
  for(let j=i+1;j<m.length&&j<=i+holdBars;j++){
   const b=m[j];
   if(j>i+1&&b.time!==m[j-1].time+TF15){
    // Market session gap: close at final actual prior observed close,
    // not at nonexistent Friday -> Monday synthetic candle.
    const prev=m[j-1];
    exit=prev.close;exitAt=prev.time+TF15;reason="SESSION_END";
    closedIndex=j-1;break;
   }
   const stopHit=side===1?b.low<=stop:b.high>=stop;
   const targetHit=side===1?b.high>=target:b.low<=target;
   if(stopHit){
    exit=side===1?Math.min(b.open,stop):Math.max(b.open,stop);
    exitAt=b.time+TF15;reason=targetHit?"STOP_FIRST_BOTH":"STOP";
    closedIndex=j;break;
   }
   if(targetHit){
    exit=target;exitAt=b.time+TF15;reason="TARGET";
    closedIndex=j;break;
   }
   if(j===i+holdBars||j===m.length-1){
    exit=b.close;exitAt=b.time+TF15;reason="TIME";
    closedIndex=j;break;
   }
  }
  if(exit===null)continue;
  const grossR=side*(exit-entry)/risk;
  if(!Number.isFinite(grossR))throw Error("INVALID_REPLAY_R");
  trades.push({family:signal.family,side:side===1?"LONG":"SHORT",
   signalTime:t,entryTime:entryBar.time,exitTime:exitAt,
   entry,exit,stop,target,grossR,reason,
   sourceKind:signal.source_kind,sourcePdf:signal.source_pdf});
  liveThrough.set(signal.family,closedIndex+1);
 }
 const result={},families=["pdf_sweep_bos","pdf_fvg_retest"];
 for(const family of families){
  const all=trades.filter(x=>x.family===family);
  const train=all.filter(x=>x.entryTime<boundary&&x.exitTime<=boundary);
  const purged=all.filter(x=>x.entryTime<boundary&&x.exitTime>boundary);
  const oos=all.filter(x=>x.entryTime>=boundary);
  result[family]={train:metrics(train),oos:metrics(oos),
   purgedBoundary:purged.length,status:"RESEARCH_ONLY_NOT_VALIDATED",
   executionApproved:false};
 }
 return {...dataset,signalTrades:trades.length,
  skippedNoncontiguousEntryBars:skippedGaps,
  evidenceQuality:{dataVerifiedByBroker:false,source:"NEON_ARCHIVED_BROKER_OHLC",
   brokerHistoryNotExecutionReport:true,insufficientOosFamilies:families.filter(f=>result[f].oos.trades<30)},
  results:result};
}
module.exports={normalize,metrics,run};
