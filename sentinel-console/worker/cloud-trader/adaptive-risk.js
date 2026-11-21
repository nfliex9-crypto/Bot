"use strict";
/**
 * Sentinel DEMO dynamic risk allocator: deterministic CLOSED-BAR PRICE-QUALITY heuristic.
 *
 * No fixed daily order quota, fixed daily loss cut-off, or fixed global position
 * count in this module. The percentage at risk is calculated for each eligible
 * source-pattern signal; a weak setup receives zero. No claim of a proven alpha
 * probability. Not suitable for live-money trading or unverified other brokers.
 *
 * Transaction costs are NOT deducted or estimated. Historical broker fills
 * and actual quote correctness remain separate from strategy scoring.
 */
const MIN_DATA={M15:16,H1:60};
function finite(x){return typeof x==="number"&&Number.isFinite(x)?x:null}
function clamp(x,a,b){return Math.max(a,Math.min(b,x))}
function ema(values,n){
 if(!Array.isArray(values)||values.length<n||values.some(x=>!Number.isFinite(x)))return null;
 const k=2/(n+1);let v=values.slice(0,n).reduce((a,b)=>a+b,0)/n;
 for(const x of values.slice(n))v+=k*(x-v);
 return v;
}
function atr(bars){
 if(!Array.isArray(bars)||bars.length<MIN_DATA.M15)return null;
 let total=0;
 for(let i=bars.length-14;i<bars.length;i++){
  const x=bars[i],p=bars[i-1];
  if(!x||!p||![x.high,x.low,x.close,p.close].every(Number.isFinite))return null;
  total+=Math.max(x.high-x.low,Math.abs(x.high-p.close),Math.abs(x.low-p.close));
 }
 return total/14;
}
function evaluate({signal,m15,h1,equity,dayStartEquity,positions=[],orders=[],
                   baseRiskPct=.25}={}){
 if(!signal||![-1,1].includes(signal.side)||!Array.isArray(m15)||
    !Array.isArray(h1)||m15.length<MIN_DATA.M15||h1.length<MIN_DATA.H1||
    !(finite(equity)>0)||!(finite(baseRiskPct)>0)||
    !Array.isArray(positions)||!Array.isArray(orders)){
  return {allowed:false,reason:"ADAPTIVE_RISK_DATA_INCOMPLETE",riskPct:0};
 }
 const latest=m15.at(-1),a=atr(m15),hourAtr=atr(h1);
 if(!(a>0)||!(hourAtr>0)||!latest||
   ![latest.open,latest.high,latest.low,latest.close].every(Number.isFinite)||
   !Number.isSafeInteger(signal.bar_time)||latest.time!==signal.bar_time||
   !Number.isFinite(signal.atr)||signal.atr<=0){
  return {allowed:false,reason:"ADAPTIVE_SIGNAL_BAR_MISMATCH",riskPct:0};
 }
 if(positions.some(x=>!x||typeof x.symbol!=="string")||
    orders.some(x=>!x||typeof x.symbol!=="string")){
  return {allowed:false,reason:"PORTFOLIO_EXPOSURE_UNVERIFIED",riskPct:0};
 }
 const closes=h1.map(b=>b.close),fast=ema(closes,20),slow=ema(closes,50);
 if(fast===null||slow===null)return {allowed:false,reason:"H1_TREND_NOT_READY",riskPct:0};
 const directional=signal.side*(fast-slow)/hourAtr;
 if(!(directional>0))return {allowed:false,reason:"H1_TREND_AGAINST_SIGNAL",riskPct:0};
 // Evidence components describe *price structure*, not likelihood of profit.
 const trend=clamp(directional/1.2,0,1);
 const body=clamp(signal.side*(latest.close-latest.open)/a,0,1);
 const closeLoc=(latest.close-latest.low)/Math.max(latest.high-latest.low,1e-12);
 const location=signal.side===1?clamp(closeLoc,0,1):clamp(1-closeLoc,0,1);
 const pattern=signal.family==="pdf_sweep_bos"?0.65:
   signal.family==="pdf_fvg_retest"?0.62:0;
 const score=clamp(trend*.32+body*.28+location*.22+pattern*.18,0,1);
 if(!(score>=.44))return {allowed:false,reason:"SIGNAL_QUALITY_TOO_WEAK",
    score:Number(score.toFixed(4)),riskPct:0,
    details:{trend,body,location,pattern}};
 // Dynamic exposure dilution instead of an arbitrary global position-count ceiling.
 // No assumption that other positions have been filled at their requested price.
 const outstanding=positions.length+orders.length;
 const occupancyFactor=1/Math.sqrt(1+outstanding);
 // Relative equity drawdown de-risks continuously, no fixed daily loss ban.
 const start=finite(dayStartEquity);
 const ratio=start!==null&&start>0?clamp(equity/start,0,1):1;
 const drawdownFactor=Math.pow(ratio,2);
 // Heuristic risk: verified broker baseline 0.25%, adapt per signal. Remains
 // proportional to equity and never attempts unbounded lot sizes.
 const qualityFactor=0.4+score*1.8;
 const pct=baseRiskPct*qualityFactor*occupancyFactor*drawdownFactor;
 if(!(pct>0)||!Number.isFinite(pct))return {allowed:false,reason:"RISK_BUDGET_UNAVAILABLE",riskPct:0};
 return {allowed:true,reason:"ADAPTIVE_PRICE_SIGNAL",score:Number(score.toFixed(4)),
  riskPct:Number(pct.toFixed(6)),openExposureCount:outstanding,
  relativeEquityRatio:Number(ratio.toFixed(5)),
  details:{trend:Number(trend.toFixed(4)),body:Number(body.toFixed(4)),
    location:Number(location.toFixed(4)),pattern}};
}
module.exports={evaluate,ema,atr};
