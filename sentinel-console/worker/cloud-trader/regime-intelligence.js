"use strict";
/**
 * Sentinel Adaptive Intelligence V2 — OHLC regime observations.
 * Input: strictly increasing, CLOSED broker M15/H1 candles only.
 * Output: deterministic descriptive features; never a profit probability.
 * All metrics use bars at or before the last input bar; no future data.
 * Zero simulated transaction-cost deductions. Research/demo only.
 */
const REQUIRED_M15=50,REQUIRED_H1=60;
const clamp=(v,lo,hi)=>Math.max(lo,Math.min(hi,v));
function validBars(bars,min){
 if(!Array.isArray(bars)||bars.length<min)return false;
 let prev=-Infinity;
 for(const b of bars){
  if(!b||!Number.isSafeInteger(b.time)||b.time<=prev||
     ![b.open,b.high,b.low,b.close].every(x=>typeof x==="number"&&Number.isFinite(x))||
     b.low<=0||b.low>Math.min(b.open,b.close)||b.high<Math.max(b.open,b.close))return false;
  prev=b.time;
 }
 return true;
}
function ema(values,n){
 if(values.length<n)return null;
 const k=2/(n+1);
 let e=values.slice(0,n).reduce((s,x)=>s+x,0)/n;
 for(const x of values.slice(n))e+=k*(x-e);
 return e;
}
function atr14(bars){
 if(bars.length<15)return null;
 let sum=0;
 for(let i=bars.length-14;i<bars.length;i++){
  const b=bars[i],p=bars[i-1];
  sum+=Math.max(b.high-b.low,Math.abs(b.high-p.close),Math.abs(b.low-p.close));
 }
 return sum/14;
}
function efficiency(closes,n=20){
 if(closes.length<n+1)return null;
 const s=closes.slice(-n-1);
 let path=0;for(let i=1;i<s.length;i++)path+=Math.abs(s[i]-s[i-1]);
 return path>0?clamp(Math.abs(s.at(-1)-s[0])/path,0,1):0;
}
function analyze(m15,h1){
 if(!validBars(m15,REQUIRED_M15)||!validBars(h1,REQUIRED_H1))
  return {ok:false,reason:"REGIME_BARS_INCOMPLETE_OR_INVALID",regime:"UNKNOWN"};
 const mClose=m15.map(x=>x.close),hClose=h1.map(x=>x.close);
 const a=atr14(m15),prevA=atr14(m15.slice(0,-14)),hourA=atr14(h1);
 if(!(a>0)||!(prevA>0)||!(hourA>0))
  return {ok:false,reason:"REGIME_ATR_UNAVAILABLE",regime:"UNKNOWN"};
 const hFast=ema(hClose,20),hSlow=ema(hClose,50),mFast=ema(mClose,20),mSlow=ema(mClose,50);
 const hDirection=Math.sign(hFast-hSlow),mDirection=Math.sign(mFast-mSlow);
 const hStrength=Math.abs(hFast-hSlow)/hourA;
 const er=efficiency(mClose,20),expansion=a/prevA;
 const last=m15.at(-1),prior=m15.at(-2);
 const shock=Math.max(last.high-last.low,Math.abs(last.high-prior.close),Math.abs(last.low-prior.close))/a;
 const aligned=hDirection!==0&&hDirection===mDirection;
 let regime="TRANSITION";
 if(expansion>=1.8||shock>=3.2)regime="VOLATILE";
 else if(er>=.36&&hStrength>=.55&&aligned)regime="TRENDING";
 else if(er<=.24&&hStrength<1.4)regime="RANGING";
 // Research hypotheses only; risk multipliers are not calibrated to profitability.
 const riskFactor={TRENDING:1.1,RANGING:.65,TRANSITION:.6,VOLATILE:.25}[regime];
 return {ok:true,regime,reason:"CLOSED_OHLC_REGIME_OBSERVATION",riskFactor,
  h1Direction:hDirection,m15Direction:mDirection,aligned,
  metrics:{efficiency:Number(er.toFixed(4)),atrExpansion:Number(expansion.toFixed(4)),
   shockRatio:Number(shock.toFixed(4)),h1TrendAtr:Number(hStrength.toFixed(4)),
   m15Atr:Number(a.toPrecision(8)),h1Atr:Number(hourA.toPrecision(8))},
  evidence:"BROKER_CLOSED_OHLC_ONLY_NOT_EXECUTED_ORDERFLOW",
  executionVerified:false};
}
module.exports={analyze,validBars,ema,atr14,efficiency};
