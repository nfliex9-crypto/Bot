"use strict";
/**
 * Deterministic gross-only broker OHLC research replay.
 * Source patterns are computed on completed M15/H1 bars, next M15 open
 * is the hypothetical entry, stop-first on ambiguous bars, no overlapping
 * trades and no cross-split label leakage. No modeled trading costs.
 * This is NOT broker execution, profit verification or live-trade approval.
 */
const source=require("../worker/cloud-trader/source-signals.js");
const adaptive=require("../worker/cloud-trader/adaptive-risk.js");
const M=900000,H=3600000;
const finite=x=>typeof x==="number"&&Number.isFinite(x);
function verify(bars,period){
 if(!Array.isArray(bars)||!bars.length)throw Error("REPLAY_BARS_REQUIRED");
 let prev=-Infinity;
 for(const b of bars){
  if(!b||!Number.isSafeInteger(b.time)||b.time<=prev||b.time%period!==0||
    ![b.open,b.high,b.low,b.close].every(finite)||b.low<=0||
    b.high<Math.max(b.open,b.close)||b.low>Math.min(b.open,b.close))
   throw Error("REPLAY_INVALID_BARS");
  prev=b.time;
 }
}
function continuous(bars,period,n){
 if(bars.length<n)return false;
 for(let i=bars.length-n+1;i<bars.length;i++)if(bars[i].time-bars[i-1].time!==period)return false;
 return true;
}
function summarize(trades){
 const r=trades.map(x=>x.grossR);let total=0,peak=0,maxDd=0,gain=0,loss=0,wins=0;
 let equity=1;
 for(let i=0;i<r.length;i++){
  const x=r[i];total+=x;peak=Math.max(peak,total);maxDd=Math.max(maxDd,peak-total);
  if(x>0){gain+=x;wins++}else loss-=x;
  equity*=Math.max(0,1+x*trades[i].riskPct/100);
 }
 const round=x=>Number(x.toFixed(5));
 return {trades:r.length,winPct:r.length?round(100*wins/r.length):null,
  grossTotalR:round(total),grossExpectancyR:r.length?round(total/r.length):null,
  grossProfitFactor:loss>0?round(gain/loss):null,
  maxDrawdownR:round(maxDd),hypotheticalGrossEquityReturnPct:round((equity-1)*100),
  independentEntryDays:new Set(trades.map(x=>new Date(x.entryTime).toISOString().slice(0,10))).size};
}
function replay({symbol,m15,h1,asOf=Date.now(),splitFraction=.7,
 embargoBars=12,holdBars=12,riskPct=.25,
 signalFn=source.researchSignal,gateFn=null}={}){
 if(typeof symbol!=="string"||!symbol||!Number.isSafeInteger(asOf)||
    !finite(splitFraction)||splitFraction<=.5||splitFraction>=.9||
    !Number.isInteger(embargoBars)||embargoBars<holdBars||
    !Number.isInteger(holdBars)||holdBars<1||holdBars>100||
    !finite(riskPct)||riskPct<=0||riskPct>1||
    typeof signalFn!=="function"||(gateFn!==null&&typeof gateFn!=="function"))
   throw Error("REPLAY_INVALID_OPTIONS");
 verify(m15,M);verify(h1,H);
 if(m15.at(-1).time+M>asOf||h1.at(-1).time+H>asOf)
  throw Error("REPLAY_FUTURE_BARS");
 const splitIndex=Math.floor(m15.length*splitFraction);
 const cutoff=m15[splitIndex]?.time;
 if(!Number.isSafeInteger(cutoff))throw Error("REPLAY_SPLIT_UNAVAILABLE");
 const segments=[{name:"TRAIN",start:0,end:splitIndex-embargoBars-1},
  {name:"OOS",start:splitIndex,end:m15.length-1}];
 const output=[];
 for(const seg of segments){
  const trades=[],skipped={gaps:0,noH1:0,noSignal:0,gate:0,incomplete:0};
  let hPtr=0;
  for(let i=Math.max(seg.start,110);i<seg.end-holdBars;i++){
   const now=m15[i].time+M;
   while(hPtr<h1.length&&h1[hPtr].time+H<=now)hPtr++;
   if(hPtr<90){skipped.noH1++;continue}
   const m=m15.slice(Math.max(0,i-149),i+1),h=h1.slice(Math.max(0,hPtr-100),hPtr);
   if(!continuous(m,M,32)||!continuous(h,H,16)){skipped.gaps++;continue}
   const signal=signalFn(symbol,m,h,now,{});
   if(!signal){skipped.noSignal++;continue}
   if(signal.symbol!==symbol||signal.bar_time!==m.at(-1).time||
      ![-1,1].includes(signal.side)||!finite(signal.atr)||
      !finite(signal.stop_atr)||!finite(signal.reward_r)||
      signal.atr<=0||signal.stop_atr<=0||signal.reward_r<=0){
    skipped.incomplete++;continue
   }
   let appliedRisk=riskPct;
   if(gateFn){
    const gate=gateFn({signal,m15:m,h1:h,equity:5000,
     dayStartEquity:5000,positions:[],orders:[],baseRiskPct:riskPct});
    if(!gate?.allowed){skipped.gate++;continue}
    appliedRisk=gate.riskPct;
    if(!finite(appliedRisk)||appliedRisk<=0||appliedRisk>riskPct+1e-8)
     throw Error("REPLAY_RISK_EXCEEDS_AUTHORIZED_CEILING");
   }
   const entryBar=m15[i+1];
   if(entryBar.time!==m15[i].time+M){skipped.gaps++;continue}
   const entry=entryBar.open,distance=signal.atr*signal.stop_atr,
     sl=entry-signal.side*distance,tp=entry+signal.side*distance*signal.reward_r;
   let exitIndex=-1,exitPrice=null,reason=null,invalid=false;
   for(let j=i+1;j<=i+holdBars;j++){
    const b=m15[j];
    if(j>i+1&&b.time-m15[j-1].time!==M){invalid=true;break}
    const hitStop=signal.side===1?b.low<=sl:b.high>=sl;
    const hitTarget=signal.side===1?b.high>=tp:b.low<=tp;
    if(hitStop){exitIndex=j;exitPrice=sl;reason="STOP_FIRST";break}
    if(hitTarget){exitIndex=j;exitPrice=tp;reason="TARGET";break}
    if(j===i+holdBars){exitIndex=j;exitPrice=b.close;reason="TIME_EXIT"}
   }
   if(invalid||exitIndex<0){skipped.incomplete++;continue}
   const grossR=signal.side*(exitPrice-entry)/distance;
   trades.push({family:signal.family,side:signal.side,entryTime:entryBar.time,
    exitTime:m15[exitIndex].time+M,grossR:Number(grossR.toFixed(8)),
    riskPct:appliedRisk,exitReason:reason});
   i=exitIndex;
  }
  output.push({window:seg.name,firstBar:m15[seg.start]?.time||null,
   lastBar:m15[seg.end]?.time||null,summary:summarize(trades),
   skipped,byFamily:Object.fromEntries([...new Set(trades.map(x=>x.family))]
    .sort().map(f=>[f,summarize(trades.filter(x=>x.family===f))])),
   trades});
 }
 return {symbol,source:"SENTINEL_BROKER_OHLC_TABLE",mode:gateFn?"ADAPTIVE_V2":"SOURCE_ONLY",
  splitTime:cutoff,embargoBars,holdBars,costDeductions:0,
  entryRule:"NEXT_M15_OPEN",ambiguousBarRule:"STOP_FIRST",
  executionEnabled:false,train:output[0],oos:output[1]};
}
module.exports={verify,continuous,summarize,replay,adaptiveGate:adaptive.evaluate};
