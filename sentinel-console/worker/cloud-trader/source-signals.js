"use strict";
/**
 * Source-derived, CLOSED-BAR M15/H1 DEMO entry hypotheses.
 * Research education is not proven orderflow, stop liquidity, or alpha.
 * Reuses the same deterministic OHLC price-pattern detector as the research lab.
 * Does NOT consume any unverified AMT video transcript or counterfeit DOM data.
 */
const patterns=require("../../brain/source-patterns.js");
const RULES=Object.freeze({
  pdf_sweep_bos:{pdf:"Market_Structure_And_Powerful_Setups_By_Wade_Fx_Setups1_1.pdf",pages:[80,81,88],stop_atr:1.7,reward_r:2},
  pdf_fvg_retest:{pdf:"9. Price_Action_Imbalance.pdf",pages:[2,3],stop_atr:1.5,reward_r:2}
});
function ema(values,n){
 if(values.length<n)return null;
 let v=values.slice(0,n).reduce((s,x)=>s+x,0)/n,k=2/(n+1);
 for(let i=n;i<values.length;i++)v+=(values[i]-v)*k;
 return v;
}
function atr14(bars){
 if(bars.length<16)return null;
 let t=0;
 for(let i=bars.length-14;i<bars.length;i++){
  const b=bars[i],p=bars[i-1];
  t+=Math.max(b.high-b.low,Math.abs(b.high-p.close),Math.abs(b.low-p.close));
 }
 return t/14;
}
function researchSignal(symbol,m15,h1,now=Date.now(),priorities={}){
 if(!Array.isArray(m15)||!Array.isArray(h1)||m15.length<110||h1.length<90)return null;
 const i=m15.length-1,last=m15[i],prev=m15[i-1];
 if(!Number.isSafeInteger(last?.time)||!Number.isSafeInteger(h1.at(-1)?.time)||
    last.time+900000>now||now-(last.time+900000)>16*60000||
    h1.at(-1).time+3600000>now||now-(h1.at(-1).time+3600000)>4*3600000)return null;
 const av=atr14(m15),trend=ema(h1.map(x=>x.close),20),slow=ema(h1.map(x=>x.close),50);
 if(!(av>0)||trend===null||slow===null||trend===slow)return null;
 const bias=trend>slow?1:-1;
 const bars=m15.map(b=>({timestamp:b.time,open:b.open,high:b.high,low:b.low,close:b.close}));
 const candidates=[];
 function result(family,side,sourceBar){
  const r=RULES[family];
  return {symbol,family,side,bar_time:last.time,reference_close:last.close,atr:av,
   stop_atr:r.stop_atr,reward_r:r.reward_r,source_kind:"OWNER_PDF_PRICE_PATTERN",
   source_pdf:r.pdf,source_pages:r.pages,source_bar_time:sourceBar,
   evidence:"CLOSED_OHLC_ONLY_NOT_VERIFIED_ORDER_FLOW",edge_verified:false};
 }
 // First require a documented local sweep, then a NEW structural confirmation
 // candle that closes beyond the sweep candle in the H1 trend direction.
 const sweeps=patterns.at(bars,i-1,{lookback:16}).filter(e=>e.family==="sweep_reclaim");
 for(const e of sweeps){
  const side=e.side==="LONG"?1:-1;
  if(side!==bias)continue;
  if(side===1&&last.close>prev.high&&last.close>last.open||
     side===-1&&last.close<prev.low&&last.close<last.open)
   candidates.push(result("pdf_sweep_bos",side,prev.time));
 }
 // First-retest of a historical 3-bar wick gap, sign of H1 trend confirmed.
 // No touches between gap formation and the current closed signal bar.
 for(let j=i-3;j>=Math.max(20,i-26);j--){
  const found=patterns.at(bars,j,{lookback:16,minGap:av*.1})
   .filter(e=>e.family==="fvg_three_candle"&&(e.side==="LONG"?1:-1)===bias);
  for(const e of found){
   const lower=e.side==="LONG"?e.level:e.level-e.gap;
   const upper=e.side==="LONG"?e.level+e.gap:e.level;
   const intervening=bars.slice(j+1,i);
   if(bias===1&&intervening.every(b=>b.low>upper)&&
      last.low<=upper&&last.low>=lower-av*.2&&
      last.close>upper&&last.close>last.open)
    candidates.push(result("pdf_fvg_retest",1,bars[j].timestamp));
   if(bias===-1&&intervening.every(b=>b.high<lower)&&
      last.high>=lower&&last.high<=upper+av*.2&&
      last.close<lower&&last.close<last.open)
    candidates.push(result("pdf_fvg_retest",-1,bars[j].timestamp));
  }
 }
 const allowed=candidates.filter(s=>priorities[s.family]!==0);
 if(!allowed.length)return null;
 allowed.sort((a,b)=>((priorities[b.family]??1)-(priorities[a.family]??1))||
   ((a.family==="pdf_sweep_bos"?-1:1)-(b.family==="pdf_sweep_bos"?-1:1)));
 const best=allowed[0];
 return {...best,weekly_priority:priorities[best.family]??1};
}
module.exports={RULES,researchSignal,atr14,ema};
