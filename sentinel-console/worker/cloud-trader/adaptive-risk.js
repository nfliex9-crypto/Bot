"use strict";
/**
 * Sentinel Adaptive Intelligence V2 — DEMO/research decision allocation.
 * Closed OHLC observations are NOT win probabilities or proven edge.
 * No daily entry quota, fixed daily loss gate or global position-count cap.
 * Exposure and equity deterioration continuously reduce proposed risk.
 * Never estimates/deducts spread, commission, swaps or slippage.
 */
const regime=require("./regime-intelligence.js");
const finite=x=>typeof x==="number"&&Number.isFinite(x)?x:null;
const clamp=(x,lo,hi)=>Math.max(lo,Math.min(hi,x));
function evaluate({signal,m15,h1,equity,dayStartEquity,positions=[],orders=[],baseRiskPct=.25}={}){
 if(!signal||![-1,1].includes(signal.side)||!(finite(equity)>0)||
    !(finite(dayStartEquity)>0)||!(finite(baseRiskPct)>0)||
    !Array.isArray(positions)||!Array.isArray(orders))
  return {allowed:false,reason:"ADAPTIVE_RISK_DATA_INCOMPLETE",riskPct:0};
 const market=regime.analyze(m15,h1);
 if(!market.ok)return {allowed:false,reason:market.reason,riskPct:0,market};
 const latest=m15.at(-1),a=regime.atr14(m15);
 if(!Number.isSafeInteger(signal.bar_time)||latest.time!==signal.bar_time||
    h1.at(-1).time>latest.time||!Number.isFinite(signal.atr)||signal.atr<=0||
    !(a>0)||signal.atr/a<.5||signal.atr/a>2)
  return {allowed:false,reason:"ADAPTIVE_SIGNAL_BAR_MISMATCH",riskPct:0,market};
 if([...positions,...orders].some(x=>!x||typeof x.symbol!=="string"||!x.symbol))
  return {allowed:false,reason:"PORTFOLIO_EXPOSURE_UNVERIFIED",riskPct:0,market};
 if(market.h1Direction!==signal.side)
  return {allowed:false,reason:"H1_TREND_AGAINST_SIGNAL",riskPct:0,market};
 const pattern={pdf_sweep_bos:.65,pdf_fvg_retest:.62}[signal.family];
 if(!pattern)return {allowed:false,reason:"UNKNOWN_STRATEGY_FAMILY",riskPct:0,market};
 const trend=clamp(market.metrics.h1TrendAtr/1.2,0,1);
 const body=clamp(signal.side*(latest.close-latest.open)/a,0,1);
 const closeLocation=clamp((latest.close-latest.low)/Math.max(latest.high-latest.low,1e-12),0,1);
 const location=signal.side===1?closeLocation:1-closeLocation;
 const regimeFit=market.regime==="TRENDING"?1:market.regime==="TRANSITION"?.65:
   market.regime==="RANGING"?(signal.family==="pdf_sweep_bos"?.45:.2):.15;
 const score=clamp(trend*.28+body*.22+location*.18+pattern*.14+regimeFit*.18,0,1);
 const quality={trend:Number(trend.toFixed(4)),body:Number(body.toFixed(4)),
  location:Number(location.toFixed(4)),pattern,regimeFit};
 if(score<.5)return {allowed:false,reason:"SIGNAL_QUALITY_TOO_WEAK",riskPct:0,
  score:Number(score.toFixed(4)),market,quality};
 const exposureCount=positions.length+orders.length;
 const occupancyFactor=1/Math.sqrt(1+exposureCount);
 const relativeEquity=clamp(equity/dayStartEquity,0,1);
 const drawdownFactor=relativeEquity**2;
 // The configured DEMO risk percentage is an authorization CEILING,
 // never a target that a heuristic score may multiply above permission.
 const qualityFactor=.25+score*.75;
 const appliedRegimeFactor=Math.min(1,market.riskFactor);
 const riskPct=baseRiskPct*qualityFactor*appliedRegimeFactor*occupancyFactor*drawdownFactor;
 if(!Number.isFinite(riskPct)||riskPct<=0||riskPct>=100)
  return {allowed:false,reason:"RISK_BUDGET_UNAVAILABLE",riskPct:0,
   score:Number(score.toFixed(4)),market,quality};
 return {allowed:true,reason:"V2_CLOSED_BAR_QUALITY",score:Number(score.toFixed(4)),
  riskPct:Number(riskPct.toFixed(6)),market,quality,
  openExposureCount:exposureCount,relativeEquityRatio:Number(relativeEquity.toFixed(5)),
  riskFactors:{quality:Number(qualityFactor.toFixed(4)),regime:appliedRegimeFactor,
   exposure:Number(occupancyFactor.toFixed(4)),drawdown:Number(drawdownFactor.toFixed(4))},
  evidence:"PRICE_ONLY_HEURISTIC_NOT_CALIBRATED_WIN_PROBABILITY",
  executionEnabled:false};
}
module.exports={evaluate,ema:regime.ema,atr:regime.atr14};
