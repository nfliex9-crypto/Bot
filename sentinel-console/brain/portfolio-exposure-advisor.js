"use strict";
/**
 * Sentinel V2 portfolio co-movement RESEARCH ADVISOR (no broker orders).
 * Estimates signed H1 return correlations from timestamp-matched, completed
 * same-venue candles; looks at the real risk-at-stop in account currency.
 * Does NOT conflate position count with actual account risk. Does not call
 * broker, route orders, invent missing risk, or deduct transaction costs.
 *
 * Correlation is descriptive and unstable in crises, NOT proof of hedging.
 * A missing exposure risk or matched price series fails closed in research.
 */
const PERIOD=3600000;
const num=x=>typeof x==="number"&&Number.isFinite(x);
const round=(x,n=4)=>Number(x.toFixed(n));
function returns(bars,asOf){
 if(!Array.isArray(bars)||bars.length<2||!Number.isSafeInteger(asOf))return null;
 const out=new Map();let last=-Infinity,p=null;
 for(const b of bars){
  if(!Number.isSafeInteger(b?.time)||b.time<=last||b.time+PERIOD>asOf||
     !num(b.close)||b.close<=0)return null;
  if(p&&b.time===last+PERIOD){
   const r=Math.log(b.close/p.close);
   if(!num(r))return null;
   out.set(b.time+PERIOD,r);
  }
  last=b.time;p=b;
 }
 return out;
}
function correlation(a,b,{minSamples=75}={}){
 if(!(a instanceof Map)||!(b instanceof Map))return {ready:false,reason:"NO_VERIFIED_H1_RETURNS",count:0};
 const x=[],y=[];
 for(const [time,r] of a){const z=b.get(time);if(num(z)){x.push(r);y.push(z)}}
 const n=x.length;
 if(n<minSamples)return {ready:false,reason:"INSUFFICIENT_MATCHED_H1",count:n};
 const mx=x.reduce((s,z)=>s+z,0)/n,my=y.reduce((s,z)=>s+z,0)/n;
 let cov=0,vx=0,vy=0;
 for(let i=0;i<n;i++){
  const dx=x[i]-mx,dy=y[i]-my;
  cov+=dx*dy;vx+=dx*dx;vy+=dy*dy;
 }
 if(!(vx>0&&vy>0))return {ready:false,reason:"DEGENERATE_RETURN_VARIANCE",count:n};
 return {ready:true,count:n,value:round(Math.max(-1,Math.min(1,cov/Math.sqrt(vx*vy))),6)};
}
function assess({accountId,equity,proposal,positions=[],histories={},
                 asOf=Date.now(),minSamples=75}={}){
 if(typeof accountId!=="string"||!accountId||!num(equity)||equity<=0||
    !proposal||!num(proposal.riskAtStop)||proposal.riskAtStop<=0||
    !["LONG","SHORT"].includes(proposal.side)||typeof proposal.symbol!=="string"||
    !Array.isArray(positions)||!Number.isSafeInteger(asOf)||
    !Number.isSafeInteger(minSamples)||minSamples<20)
  return {ready:false,reason:"PORTFOLIO_INPUT_INCOMPLETE",riskMultiplier:0};
 if(proposal.accountId!==accountId||
    positions.some(p=>!p||p.accountId!==accountId||
      !num(p.riskAtStop)||p.riskAtStop<0||
      typeof p.symbol!=="string"||!["LONG","SHORT"].includes(p.side)))
  return {ready:false,reason:"PORTFOLIO_RISK_UNVERIFIED",riskMultiplier:0};
 const symbols=new Set([proposal.symbol,...positions.map(x=>x.symbol)]),maps=new Map();
 for(const symbol of symbols){
  const series=returns(histories[symbol],asOf);
  if(!series||series.size<minSamples){
   return {ready:false,reason:"MISSING_MATCHED_BROKER_HISTORY",
    missingSymbol:symbol,riskMultiplier:0};
  }
  maps.set(symbol,series);
 }
 let alignedRisk=0,results=[];
 for(const p of positions){
  if(p.riskAtStop===0)continue;
  const corr=p.symbol===proposal.symbol?{ready:true,count:maps.get(p.symbol).size,value:1}:
   correlation(maps.get(proposal.symbol),maps.get(p.symbol),{minSamples});
  if(!corr.ready)return {ready:false,reason:"CORRELATION_NOT_ESTIMABLE",
    missingPair:[proposal.symbol,p.symbol],detail:corr.reason,riskMultiplier:0};
  const direction=proposal.side===p.side?1:-1;
  const directionalCorr=Math.max(0,corr.value*direction);
  alignedRisk+=p.riskAtStop*directionalCorr;
  results.push({symbol:p.symbol,side:p.side,riskAtStop:p.riskAtStop,
   correlatedSigned:round(corr.value*direction,4),
   matchedH1:corr.count});
 }
 // Reduces risk continuously without a hard position count.
 // This is a heuristic *penalty*, not a Monte Carlo VaR or loss guarantee.
 const multiplier=1/Math.sqrt(1+alignedRisk/proposal.riskAtStop);
 const totalWorstStop=proposal.riskAtStop+
   positions.reduce((s,p)=>s+p.riskAtStop,0);
 return {ready:true,reason:"RESEARCH_CORRELATION_PENALTY",
  riskMultiplier:round(multiplier,6),
  proposedRiskAtStop:proposal.riskAtStop,
  existingRiskAtStop:round(totalWorstStop-proposal.riskAtStop,2),
  grossCombinedStopExposurePct:round(totalWorstStop/equity*100,4),
  alignedRiskAmount:round(alignedRisk,2),
  observations:results,executionApproved:false,
  warnings:["CORRELATION_CAN_CHANGE","GAP_LOSS_CAN_EXCEED_STOP_RISK",
            "NOT_A_CALIBRATED_VAR_MODEL"],
  deductionsApplied:0};
}
module.exports={PERIOD,returns,correlation,assess};
