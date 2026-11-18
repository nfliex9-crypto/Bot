"use strict";
/*
 * Sentinel Intelligence Core v1 — pure, deterministic, read-only quantitative lab.
 * Inputs: broker OHLC and *completed* broker trade history. Outputs: research
 * scores and paper-only rankings. No trading APIs, no synthetic candles,
 * no future-bar signals or use of backtest labels as forward evidence.
 */
const VERSION="brain-research-v1";
const STRATEGIES=[
 {id:"ema_pullback",label:"EMA pullback",family:"trend"},
 {id:"donchian_breakout",label:"Donchian breakout",family:"breakout"},
 {id:"rsi_mean_reversion",label:"RSI mean reversion",family:"range"},
 {id:"volatility_expansion",label:"Volatility expansion",family:"momentum"}
];
function n(x){if(x===null||x===undefined||x===""||typeof x==="boolean")return null;const v=Number(x);return Number.isFinite(v)?v:null}
function mean(xs){return xs.length?xs.reduce((s,x)=>s+x,0)/xs.length:0}
function std(xs){if(xs.length<2)return 0;const m=mean(xs);return Math.sqrt(xs.reduce((s,v)=>s+(v-m)**2,0)/(xs.length-1))}
function median(xs){if(!xs.length)return 0;const a=[...xs].sort((x,y)=>x-y),k=a.length>>1;return a.length%2?a[k]:(a[k-1]+a[k])/2}
function timeMs(t){
 if(typeof t==="number"&&Number.isFinite(t))return t<1e11?t*1000:t;
 const d=Date.parse(String(t||""));return Number.isFinite(d)?d:null;
}
function normalizeCandles(input){
 if(!Array.isArray(input))throw Error("CANDLES_MUST_BE_ARRAY");
 const byTime=new Map();let rejected=0,missingSpread=0;
 for(const bar of input){
  const ts=timeMs(bar.timestamp??bar.time),open=n(bar.open),high=n(bar.high),low=n(bar.low),close=n(bar.close);
  if(ts===null||open===null||high===null||low===null||close===null||
    low<=0||low>Math.min(open,close)||high<Math.max(open,close)||high<low){
    rejected++;continue;
  }
  const spread=n(bar.spread);
  if(spread===null||spread<=0)missingSpread++;
  byTime.set(ts,{timestamp:ts,open,high,low,close,
   spread:spread!==null&&spread>0?spread:null,
   tickVolume:n(bar.tickVolume??bar.tick_volume)});
 }
 const bars=[...byTime.values()].sort((a,b)=>a.timestamp-b.timestamp);
 const gapCount=bars.length>2?bars.slice(1).filter((b,i)=>b.timestamp<=bars[i].timestamp).length:0;
 return {bars,quality:{raw_rows:input.length,valid_rows:bars.length,rejected_rows:rejected,
  duplicate_rows:input.length-rejected-bars.length,missing_spread_rows:bars.filter(b=>b.spread===null).length,
  missing_spread_ratio:bars.length?bars.filter(b=>b.spread===null).length/bars.length:1,
  out_of_order_or_duplicate_timestamps:gapCount}};
}
function normalizeClosedTrade(x){
 if(!x||typeof x!=="object")return null;
 const ticket=String(x.ticket||"").trim(),symbol=String(x.symbol||"").trim();
 const closed=timeMs(x.closeTime);
 if(!ticket||!symbol||closed===null)return null;
 const profit=n(x.profit),complete=x.complete===true&&profit!==null;
 return {
  ticket,closeTime:new Date(closed).toISOString(),
  openTime:timeMs(x.openTime)===null?null:new Date(timeMs(x.openTime)).toISOString(),
  symbol:symbol.slice(0,28),side:String(x.side||"").slice(0,8),
  volume:n(x.volume),openPrice:n(x.openPrice),closePrice:n(x.closePrice),
  brokerProfit:complete?profit:null,swap:n(x.swap),commission:n(x.commission),
  complete, strategyId:null,attribution:"unattributed",
  costsVerified:false
 };
}
function reviewRealTrades(raw){
 const rows=(raw||[]).filter(r=>r.complete===true&&n(r.brokerProfit)!==null);
 const vals=rows.map(r=>Number(r.brokerProfit));
 const wins=vals.filter(v=>v>0),losses=vals.filter(v=>v<0);
 let equity=0,peak=0,drawdown=0;
 for(const v of vals){equity+=v;peak=Math.max(peak,equity);drawdown=Math.max(drawdown,peak-equity)}
 return {total_records:(raw||[]).length,completed_records:rows.length,
  incomplete_records:(raw||[]).length-rows.length,unattributed_records:rows.filter(r=>!r.strategyId).length,
  recorded_broker_profit:vals.reduce((a,b)=>a+b,0),
  win_rate:vals.length?wins.length/vals.length:null,
  profit_factor:losses.length?wins.reduce((a,b)=>a+b,0)/Math.abs(losses.reduce((a,b)=>a+b,0)):null,
  max_recorded_drawdown:drawdown,
  note:"Broker history commission/swap values can be placeholders. Strategy attribution is NOT inferred from symbol or P/L."};
}
function indicators(bars){
 const out=[];let ema20=bars[0].close,ema50=bars[0].close,atr=bars[0].high-bars[0].low;
 let up=0,down=0;
 for(let i=0;i<bars.length;i++){
  const b=bars[i],prev=bars[i-1]||b;
  const tr=Math.max(b.high-b.low,Math.abs(b.high-prev.close),Math.abs(b.low-prev.close));
  atr=i?((atr*13)+tr)/14:tr;
  ema20=i?(b.close*2/21+ema20*19/21):b.close;
  ema50=i?(b.close*2/51+ema50*49/51):b.close;
  const gain=Math.max(0,b.close-prev.close),loss=Math.max(0,prev.close-b.close);
  up=i?(up*6+gain)/7:gain;down=i?(down*6+loss)/7:loss;
  const rsi=down===0?100:100-100/(1+up/down);
  let prevHi=-Infinity,prevLo=Infinity;
  for(let j=Math.max(0,i-20);j<i;j++){prevHi=Math.max(prevHi,bars[j].high);prevLo=Math.min(prevLo,bars[j].low)}
  out.push({ema20,ema50,atr,rsi,prevHi,prevLo,tr});
 }
 return out;
}
function signal(strategy,bars,ind,i){
 if(i<60||i>=bars.length-1)return 0;
 const bar=bars[i],prev=bars[i-1],v=ind[i],old=ind[i-1];
 if(strategy==="ema_pullback"){
  if(v.ema20>v.ema50&&prev.close<old.ema20&&bar.close>v.ema20)return 1;
  if(v.ema20<v.ema50&&prev.close>old.ema20&&bar.close<v.ema20)return -1;
 }
 if(strategy==="donchian_breakout"){
  if(v.ema20>v.ema50&&bar.close>v.prevHi&&bar.close>bar.open)return 1;
  if(v.ema20<v.ema50&&bar.close<v.prevLo&&bar.close<bar.open)return -1;
 }
 if(strategy==="rsi_mean_reversion"){
  if(v.rsi<22&&bar.close<v.ema20-v.atr*1.1)return 1;
  if(v.rsi>78&&bar.close>v.ema20+v.atr*1.1)return -1;
 }
 if(strategy==="volatility_expansion"){
  if(v.tr>old.atr*1.8&&bar.close>bar.open&&v.ema20>v.ema50&&bar.close>prev.high)return 1;
  if(v.tr>old.atr*1.8&&bar.close<bar.open&&v.ema20<v.ema50&&bar.close<prev.low)return -1;
 }
 return 0;
}
function simulateFold(bars,ind,strategy,start,end,costMultiplier=1){
 const trades=[];let position=null;
 const count=Math.min(end,bars.length);
 const epsilon=1e-10;
 for(let i=Math.max(60,start);i<count;i++){
  const b=bars[i];
  if(position&&i>=position.entryIndex){
   const {dir,entry,stop,target,initialRisk,entryIndex}=position;
   // Gap through stop fills at the adverse open, never the optimistic stop price.
   const stopHit=dir>0?b.low<=stop:b.high>=stop;
   const targetHit=dir>0?b.high>=target:b.low<=target;
   let rawExit=null,reason="";
   if(stopHit){rawExit=dir>0?Math.min(stop,b.open):Math.max(stop,b.open);reason="stop";}
   else if(targetHit){rawExit=target;reason="target";}
   else if(i-entryIndex>=36||i===count-1){rawExit=b.close;reason="time";}
   if(rawExit!==null){
    const rawSpread=(b.spread===null?Math.max(b.close*.00015,epsilon):b.spread);
    const cost=Math.max(rawSpread,b.close*.0001)*costMultiplier/2+b.close*.00002*costMultiplier;
    const exit=rawExit-dir*cost;
    const rr=(exit-entry)*dir/initialRisk;
    if(Number.isFinite(rr))trades.push({time:b.timestamp,dir,rr,reason});
    position=null;
   }
  }
  if(position||i>=count-1||!Number.isFinite(ind[i].atr)||ind[i].atr<=epsilon)continue;
  const dir=signal(strategy,bars,ind,i);
  if(!dir)continue;
  const next=bars[i+1],risk=Math.max(ind[i].atr*1.5,next.open*.00015);
  const spread=next.spread===null?next.open*.00015:next.spread;
  const entryCost=Math.max(spread,next.open*.0001)*costMultiplier/2+next.open*.00002*costMultiplier;
  const entry=next.open+dir*entryCost;
  position={dir,entry,stop:entry-dir*risk,target:entry+dir*risk*2,
   initialRisk:risk,entryIndex:i+1};
 }
 return trades;
}
function metrics(trades){
 const rr=trades.map(t=>t.rr),profit=rr.filter(v=>v>0).reduce((a,b)=>a+b,0);
 const loss=Math.abs(rr.filter(v=>v<0).reduce((a,b)=>a+b,0));
 let equity=0,peak=0,drawdown=0;
 for(const r of rr){equity+=r;peak=Math.max(peak,equity);drawdown=Math.max(drawdown,peak-equity)}
 const avg=mean(rr),dev=std(rr);
 return {trades:rr.length,expectancy_r:avg,median_r:median(rr),
  win_rate:rr.length?rr.filter(v=>v>0).length/rr.length:0,
  profit_factor:loss>0?profit/loss:null,drawdown_r:drawdown,
  sharpe_per_trade:dev>0?avg/dev:null,
  lower_confidence_expectancy_r:rr.length>=2?avg-1.28*dev/Math.sqrt(rr.length):null,
  wins:rr.filter(v=>v>0).length};
}
function research(candleInput,sourceQuality={}){
 const normalized=normalizeCandles(candleInput),bars=normalized.bars;
 const quality={...normalized.quality,source_coverage:String(sourceQuality.coverage||"unknown"),
  source_truncated:sourceQuality.truncated===true,
  source_stop_reason:sourceQuality.stopReason||null};
 if(bars.length<320)return {version:VERSION,quality,candles:bars.length,strategies:[],
  portfolio:{status:"NO_DATA",reason:"At least 320 valid candles required",weights:{}},
  execution_enabled:false,trained_on:"broker_candles_only"};
 const ind=indicators(bars),last=bars.length;
 const starts=[Math.floor(last*.4),Math.floor(last*.6),Math.floor(last*.8)];
 const ends=[Math.floor(last*.6),Math.floor(last*.8),last];
 const incomplete=quality.source_truncated||quality.source_coverage!=="complete";
 const weakCosts=quality.missing_spread_ratio>.35;
 const findings=STRATEGIES.map(({id,label,family})=>{
  const folds=starts.map((from,k)=>{
    const to=ends[k],trades=simulateFold(bars,ind,id,from,to);
    const stressed=simulateFold(bars,ind,id,from,to,2);
    return {start:new Date(bars[from].timestamp).toISOString(),end:new Date(bars[to-1].timestamp).toISOString(),
      ...metrics(trades),stress_expectancy_r:metrics(stressed).expectancy_r};
  });
  const all=starts.flatMap((from,k)=>simulateFold(bars,ind,id,from,ends[k]));
  const stressed=starts.flatMap((from,k)=>simulateFold(bars,ind,id,from,ends[k],2));
  const m=metrics(all),sm=metrics(stressed);
  const minFold=Math.min(...folds.map(f=>f.trades)),positiveFolds=folds.filter(f=>f.expectancy_r>0).length;
  // Fixed strategy rules and non-overlapping, chronological OOS windows.
  // Genuine paper promotion needs further *forward* evidence on tagged executed trades.
  let status="WATCH",reason="Insufficient confidence for paper candidate";
  if(incomplete){status="DATA_INCOMPLETE";reason="Provider truncated / incomplete candle window";}
  else if(weakCosts){status="COST_DATA_WEAK";reason="Spread missing in more than 35% of candles";}
  else if(m.trades<30||minFold<5){status="INSUFFICIENT";reason="Fewer than 30 OOS trades or fewer than 5 in a fold";}
  else if(m.expectancy_r<=0||sm.expectancy_r<=0||positiveFolds<2){
    status="PAUSE_RESEARCH";reason="Non-positive OOS or double-cost expectancy / unstable folds";
  }else if((m.lower_confidence_expectancy_r??-1)>.03&&m.drawdown_r<=12){
    status="PAPER_CANDIDATE";reason="OOS positive with evidence, stress costs, fold stability";
  }
  return {strategy_id:id,label,family,status,reason,folds,
   oos:m,double_costs:sm,positive_folds:positiveFolds,
   relative_research_priority:0};
 });
 // Per-symbol paper research priority ONLY; not lots, orders, or risk settings.
 const candidates=findings.filter(f=>f.status==="PAPER_CANDIDATE");
 if(candidates.length){
  const scores=candidates.map(f=>Math.max(.001,f.oos.lower_confidence_expectancy_r||0));
  const total=scores.reduce((a,b)=>a+b,0);
  candidates.forEach((f,i)=>{f.relative_research_priority=Math.round(scores[i]/total*1000)/1000});
 }
 return {version:VERSION,candles:bars.length,quality,strategies:findings,
  portfolio:{status:candidates.length?"PAPER_RESEARCH_CANDIDATES":"NO_PROMOTABLE_STRATEGIES",
   candidate_count:candidates.length,
   weights:Object.fromEntries(candidates.map(f=>[f.strategy_id,f.relative_research_priority])),
   execution_enabled:false},
  trained_on:"broker_candles_only",execution_enabled:false,
  disclaimer:"OOS research evidence is not real forward performance. No automatic live/demo order sizing."};
}
module.exports={VERSION,STRATEGIES,normalizeCandles,normalizeClosedTrade,reviewRealTrades,
 indicators,signal,simulateFold,metrics,research};
