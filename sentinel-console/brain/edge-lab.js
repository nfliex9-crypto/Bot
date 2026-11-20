"use strict";
/**
 * Sentinel Edge Lab v1 — original research inspired by Grok export's
 * failed-level / volatility ideas, NOT its source code or trading settings.
 * All outputs are shadow hypotheses; no orders, lot sizing, or live permissions.
 * M15 broker OHLC has no historical spread. Recent real quotes supply a
 * STRESSED COST PROXY, never a claim about historical execution costs.
 */
const FAMILY=["sweep_reclaim","compression_breakout","fvg_retest"];
const VERSION="edge-lab-2026-11-19-v1";
const TF=15*60000;
function finite(x){return typeof x==="number"&&Number.isFinite(x)}
function normalize(raw){
 if(!Array.isArray(raw))throw Error("BARS_NOT_ARRAY");
 let last=-Infinity;
 return raw.map(b=>{
  const time=typeof b.timestamp==="number"?b.timestamp:Date.parse(String(b.bar_time??b.time??""));
  const open=Number(b.open),high=Number(b.high),low=Number(b.low),close=Number(b.close);
  if(!Number.isSafeInteger(time)||time<=last||![open,high,low,close].every(finite)||
    low<=0||high<Math.max(open,close)||low>Math.min(open,close))throw Error("INVALID_BROKER_BAR");
  last=time;return {time,open,high,low,close};
 });
}
function atrAt(bars,i,n=14){
 if(i<n)return null;
 let sum=0;
 for(let j=i-n+1;j<=i;j++){
  const b=bars[j],prev=bars[j-1];
  sum+=Math.max(b.high-b.low,Math.abs(b.high-prev.close),Math.abs(b.low-prev.close));
 }
 return sum/n;
}
function emaAt(bars,i,n){
 if(i<n-1)return null;
 let v=0;for(let j=0;j<n;j++)v+=bars[j].close;v/=n;
 const k=2/(n+1);
 for(let j=n;j<=i;j++)v+=k*(bars[j].close-v);
 return v;
}
function effAt(bars,i,n=20){
 if(i<n)return null;
 let sum=0;
 for(let j=i-n+1;j<=i;j++)sum+=Math.abs(bars[j].close-bars[j-1].close);
 return sum>0?Math.abs(bars[i].close-bars[i-n].close)/sum:0;
}
function precompute(bars){
 const n=bars.length;
 const atr=Array(n).fill(null),eff=Array(n).fill(null);
 const e20=Array(n).fill(null),e50=Array(n).fill(null);
 let a20=0,a50=0;
 for(let i=0;i<n;i++){
  if(i<20)a20+=bars[i].close;
  if(i<50)a50+=bars[i].close;
  if(i===19)e20[i]=a20/20;
  else if(i>19)e20[i]=e20[i-1]+2/21*(bars[i].close-e20[i-1]);
  if(i===49)e50[i]=a50/50;
  else if(i>49)e50[i]=e50[i-1]+2/51*(bars[i].close-e50[i-1]);
  if(i>=14)atr[i]=atrAt(bars,i,14);
  if(i>=20)eff[i]=effAt(bars,i,20);
 }
 return {atr,eff,e20,e50};
}
function regimeAt(bars,i,cache=null){
 const efficiency=cache?cache.eff[i]:effAt(bars,i,20);
 const atr=cache?cache.atr[i]:atrAt(bars,i,14);
 if(efficiency===null||atr===null||atr<=0)return null;
 const samples=[];
 for(let j=Math.max(20,i-64);j<i;j+=3){
  const a=cache?cache.atr[j]:atrAt(bars,j,14);if(a>0)samples.push(a);
 }
 samples.sort((a,b)=>a-b);
 const median=samples.length?samples[Math.floor(samples.length/2)]:atr;
 const shock=atr/median;
 return {label:shock>=1.9?"SHOCK":efficiency>=.38?"TREND":
   efficiency<=.19?"RANGE":"MIXED",efficiency,atr,atrRatio:shock};
}
function signalAt(bars,i,family,cache=null){
 if(!FAMILY.includes(family)||i<100||i>=bars.length)return null;
 const b=bars[i],state=regimeAt(bars,i,cache),prior=bars.slice(i-20,i);
 if(!state||state.label==="SHOCK"||!(state.atr>0))return null;
 const top=Math.max(...prior.map(x=>x.high)),bottom=Math.min(...prior.map(x=>x.low));
 const range=Math.max(b.high-b.low,1e-12),body=Math.abs(b.close-b.open)/range;
 const ema20=cache?cache.e20[i]:emaAt(bars,i,20),ema50=cache?cache.e50[i]:emaAt(bars,i,50);
 let side=0;
 if(family==="sweep_reclaim"){
  if(state.label==="TREND")return null; // no systematic countertrend in strong trend
  if(b.high>top+state.atr*.045&&b.close<top&&
    (b.high-Math.max(b.open,b.close))/range>=.42&&b.close<b.open)side=-1;
  else if(b.low<bottom-state.atr*.045&&b.close>bottom&&
    (Math.min(b.open,b.close)-b.low)/range>=.42&&b.close>b.open)side=1;
 }else if(family==="fvg_retest"){
  // Three-candle wick non-overlap from the owner-supplied Price Action
  // Imbalance PDF (physical page 2). Test a FIRST revisit/rejection of the
  // recorded zone, never an assumed guaranteed fill or real order-flow void.
  // Signal on closed bar i, enter next bar using the existing cost proxy.
  if(state.label==="RANGE")return null;
  for(let j=i-3;j>=Math.max(52,i-28);j--){
   const a=bars[j-2],m=bars[j-1],z=bars[j];
   const bullGap=z.low>a.high+state.atr*.08&&m.close>m.open;
   const bearGap=z.high<a.low-state.atr*.08&&m.close<m.open;
   if(bullGap&&ema20>ema50&&b.low<=z.low&&b.close>z.low&&b.close>b.open){
    if(!bars.slice(j+1,i).some(x=>x.low<=z.low)){side=1;break}
   }
   if(bearGap&&ema20<ema50&&b.high>=z.high&&b.close<z.high&&b.close<b.open){
    if(!bars.slice(j+1,i).some(x=>x.high>=z.high)){side=-1;break}
   }
  }
 }else{
  // True contraction must precede the signal bar. Never include it in range.
  const recent=bars.slice(i-12,i),rh=Math.max(...recent.map(x=>x.high));
  const rl=Math.min(...recent.map(x=>x.low));
  const prevAtr=cache?cache.atr[i-1]:atrAt(bars,i-1,14);
  if(!(prevAtr>0)||(rh-rl)/prevAtr>4.4||body<.60||state.atrRatio>1.65)return null;
  if(b.close>rh+.13*prevAtr&&ema20>ema50&&state.efficiency>=.25)side=1;
  else if(b.close<rl-.13*prevAtr&&ema20<ema50&&state.efficiency>=.25)side=-1;
 }
 return side?{family,side,signal_time:b.time,atr:state.atr,regime:state.label,
   close:b.close,efficiency:Number(state.efficiency.toFixed(4))}:null;
}
function costPriceFromQuotes(quotes,model="P90"){
 const spreads=(quotes||[]).map(q=>Number(q.spread??(Number(q.ask)-Number(q.bid))))
  .filter(x=>Number.isFinite(x)&&x>0).sort((a,b)=>a-b);
 if(spreads.length<5)return null;
 const q=model==="P95"?.95:.90;
 return spreads[Math.min(spreads.length-1,Math.floor(q*(spreads.length-1)))];
}
function resolve(bars,i,signal,spread,maxHold=8){
 const entryBar=bars[i+1];
 if(!entryBar||entryBar.time-signal.signal_time!==TF)return null;
 const atr=signal.atr;
 const distance=Math.max(atr*1.5,spread*8);
 if(!(distance>0))return null;
 const side=signal.side,entry=entryBar.open+(side===1?spread:0);
 const stop=entry-side*distance,tp=entry+side*2*distance;
 let exit=null,reason="TIME",exitTime=null;
 for(let j=i+1;j<=Math.min(bars.length-1,i+maxHold);j++){
  const b=bars[j],prev=bars[j-1];
  // Missing 15-minute bar invalidates future path; do not assume a fill.
  if(b.time-prev.time!==TF)return null;
  const hi=b.high+(side===-1?spread:0);
  const lo=b.low+(side===-1?spread:0);
  const stopHit=side===1?lo<=stop:hi>=stop;
  const tpHit=side===1?hi>=tp:lo<=tp;
  if(stopHit){exit=stop;reason=tpHit?"AMBIGUOUS_STOP_FIRST":"STOP";exitTime=b.time;break}
  if(tpHit){exit=tp;reason="TARGET";exitTime=b.time;break}
  if(j===i+maxHold){exit=b.close+(side===-1?spread:0);exitTime=b.time}
 }
 if(exit===null)return null;
 return {family:signal.family,side,entry_time:entryBar.time,exit_time:exitTime,
  regime:signal.regime,r:Number((side*(exit-entry)/distance).toFixed(5)),
  exit_reason:reason,fill_quality:"BROKER_OHLC_PROXY_STOP_FIRST",
  reference_spread:spread};
}
function stats(trades){
 const rs=trades.map(x=>x.r);const n=rs.length;
 const gains=rs.filter(x=>x>0).reduce((a,b)=>a+b,0);
 const losses=-rs.filter(x=>x<0).reduce((a,b)=>a+b,0);
 const sum=rs.reduce((a,b)=>a+b,0);
 const mean=n?sum/n:null;
 const byWeek=new Map();
 for(const x of trades){const wk=Math.floor(x.entry_time/(7*86400000));byWeek.set(wk,(byWeek.get(wk)||0)+x.r)}
 const positiveWeeks=[...byWeek.values()].filter(x=>x>0).length;
 return {trades:n,expectancy_r:mean===null?null:Number(mean.toFixed(5)),
   profit_factor:losses>0?Number((gains/losses).toFixed(3)):null,
   positive_weeks:byWeek.size?Number((positiveWeeks/byWeek.size).toFixed(3)):null,
   net_r:Number(sum.toFixed(4)),stop_first_ambiguous:trades.filter(x=>x.exit_reason==="AMBIGUOUS_STOP_FIRST").length};
}
function evaluate(barsRaw,{spreads=[],minBars=480}={}){
 const bars=normalize(barsRaw);
 if(bars.length<minBars||bars.length<120)return {version:VERSION,status:"INSUFFICIENT_BARS",
   bar_count:bars.length,families:[],execution_enabled:false};
 const proxy=costPriceFromQuotes(spreads);
 if(proxy===null)return {version:VERSION,status:"MISSING_REAL_SPREAD_SAMPLE",
   bar_count:bars.length,families:[],execution_enabled:false};
 // Calendar-order partitions are fixed BEFORE evaluating candidates.
 const p1=Math.floor(bars.length*.60),p2=Math.floor(bars.length*.80);
 const boundary=[bars[p1].time,bars[p2].time];
 const cache=precompute(bars);
 const out=[];
 for(const family of FAMILY){
  const datasets={train:[],validation:[],holdout:[]};
  const stress={train:[],validation:[]};
  let lastExit=-Infinity;
  for(let i=100;i<bars.length-9;i++){
   const sig=signalAt(bars,i,family,cache);if(!sig||bars[i].time<=lastExit)continue;
   const t=resolve(bars,i,sig,proxy);
   if(!t)continue;
   const split=t.entry_time<boundary[0]?"train":t.entry_time<boundary[1]?"validation":"holdout";
   if(split==="train"&&t.exit_time>=boundary[0]||split==="validation"&&t.exit_time>=boundary[1])continue;
   datasets[split].push(t);
   // 2x observed P90 spread is a scenario, not an actual historical spread.
   if(split!=="holdout"){
    const st=resolve(bars,i,sig,proxy*2);
    if(st)stress[split].push(st);
   }
   lastExit=t.exit_time;
  }
  const train=stats(datasets.train),validation=stats(datasets.validation),
    holdout=stats(datasets.holdout),validationStress=stats(stress.validation);
  const review=train.trades>=30&&validation.trades>=15&&
    train.expectancy_r>0&&validation.expectancy_r>0&&
    (train.profit_factor??0)>1.10&&(validation.profit_factor??0)>1.05&&
    (validation.positive_weeks??0)>=.5&&validationStress.expectancy_r>0;
  out.push({family,status:review?"SHADOW_REVIEW_ELIGIBLE":"RESEARCH_UNPROVEN",
    train,validation,holdout,validation_stressed:validationStress,
    holdout_is_report_only:true,execution_enabled:false,
    signal_count:Object.values(datasets).reduce((n,x)=>n+x.length,0)});
 }
 return {version:VERSION,status:"COST_PROXY_RESEARCH_ONLY",bar_count:bars.length,
   start:new Date(bars[0].time).toISOString(),end:new Date(bars.at(-1).time).toISOString(),
   reference_spread_p90:proxy,stress_multiple:2,
   cost_notice:"Recent broker quote P90 proxy (not historical bid/ask); commissions/slippage are not fully verified",
   split:{train_end:new Date(boundary[0]).toISOString(),validation_end:new Date(boundary[1]).toISOString()},
   families:out,execution_enabled:false,broker_verified_edge:false};
}
module.exports={VERSION,FAMILY,normalize,atrAt,emaAt,precompute,regimeAt,signalAt,
  costPriceFromQuotes,resolve,stats,evaluate};
