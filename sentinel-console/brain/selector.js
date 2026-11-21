"use strict";
/*
 * Sentinel Adaptive Selector v2
 * Real, pre-attributed CLOSED demo trades -> robust strategy research weights.
 * No order routes, no lot sizing, no changes to the user's trading bot.
 * "2X" is an experiment-priority multiplier, NOT a money/risk multiplier.
 */
const {STRATEGIES}=require("./engine.js");
const ALLOWED=new Set([...STRATEGIES.map(s=>s.id),"sweep_bos_pullback"]);
const mean=xs=>xs.length?xs.reduce((a,b)=>a+b,0)/xs.length:0;
const sum=xs=>xs.reduce((a,b)=>a+b,0);
const finite=x=>{
 if(x===null||x===undefined||x===""||typeof x==="boolean")return null;
 const n=Number(x);return Number.isFinite(n)?n:null;
};
const validDate=x=>{
 const t=new Date(x).getTime();return Number.isFinite(t)?t:null;
};
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
function expectancy(trades){
 const rr=trades.map(t=>t.netR),n=rr.length;
 const wins=rr.filter(x=>x>0),losses=rr.filter(x=>x<0);
 const early=rr.slice(0,Math.floor(n/2)),recent=rr.slice(-20),last10=rr.slice(-10);
 const days=new Map();
 for(const t of trades){
  const day=new Date(t.time).toISOString().slice(0,10);
  const list=days.get(day)||[];list.push(t.netR);days.set(day,list);
 }
 // Correlated intraday trades are not independent observations.
 const daily=[...days.values()].map(mean);
 const dm=mean(daily);
 const ds=daily.length>1?Math.sqrt(sum(daily.map(x=>(x-dm)**2))/(daily.length-1)):0;
 const confidence=daily.length>=10?dm-1.645*ds/Math.sqrt(daily.length):null;
 let equity=0,peak=0,dd=0,streak=0,maxStreak=0;
 for(const v of rr){
  equity+=v;peak=Math.max(peak,equity);dd=Math.max(dd,peak-equity);
  streak=v<0?streak+1:0;maxStreak=Math.max(maxStreak,streak);
 }
 const weighted=rr.map((v,i)=>({v,w:Math.pow(.5,(n-i-1)/20)}));
 const decayed=sum(weighted.map(x=>x.v*x.w))/Math.max(1e-9,sum(weighted.map(x=>x.w)));
 const pos=sum(wins);
 return {
  count:n,active_days:days.size,mean_r:mean(rr),robust_mean_r:mean(rr),
  lower_confidence_r:confidence,early_mean_r:mean(early),
  recent_mean_r:mean(recent),last_10_mean_r:mean(last10),
  decayed_expectancy_r:decayed,profit_factor:losses.length?pos/Math.abs(sum(losses)):null,
  raw_total_r:sum(rr),max_drawdown_r:dd,max_loss_streak:maxStreak,
  largest_win_share:pos>0?Math.max(...wins)/pos:null,
  winning_days:[...days.values()].filter(x=>sum(x)>0).length
 };
}
function assessForward(trades,{symbol=null}={}){
 if(!Array.isArray(trades))throw Error("FORWARD_TRADES_EXPECTED");
 const groups=new Map();
 const quality={records:trades.length,qualified:0,untagged:0,missing_risk:0,
  invalid_tags:0,invalid_time:0,duplicates:0,filtered_other_symbols:0,clipped_outliers:0};
 const seen=new Set();
 const ordered=[...trades].sort((a,b)=>(validDate(a.closeTime)??0)-(validDate(b.closeTime)??0));
 for(const row of ordered){
  if(symbol&&row.symbol&&String(row.symbol).toUpperCase()!==String(symbol).toUpperCase()){
   quality.filtered_other_symbols++;continue;
  }
  const strategy=String(row.strategyId||"");
  if(!strategy){quality.untagged++;continue;}
  if(!ALLOWED.has(strategy)){quality.invalid_tags++;continue;}
  const profit=finite(row.brokerProfit),risk=finite(row.riskAmount);
  if(row.complete!==true||profit===null||risk===null||risk<=0){
   quality.missing_risk++;continue;
  }
  const close=validDate(row.closeTime),tagged=validDate(row.taggedAt);
  const opened=row.openTime?validDate(row.openTime):null;
  if(close===null||tagged===null||tagged>=close||(opened!==null&&tagged<opened)){
   quality.invalid_tags++;quality.invalid_time++;continue;
  }
  if(row.ticket!==undefined&&row.ticket!==null){
   const identity=String(row.ticket)+"|"+String(close);
   if(seen.has(identity)){quality.duplicates++;continue;}
   seen.add(identity);
  }
  quality.qualified++;
  // Winsorize extreme R outcomes for LEARNING only; raw broker P/L remains unchanged in Neon.
  const rawR=profit/risk;
  const netR=clamp(rawR,-5,5);
  if(netR!==rawR)quality.clipped_outliers++;
  const list=groups.get(strategy)||[];
  list.push({time:close,netR});groups.set(strategy,list);
 }
 const strategy_results=[];
 for(const strategy of ALLOWED){
  const data=groups.get(strategy)||[],m=expectancy(data);
  let status="COLLECTING_FORWARD",multiplier=1;
  let reason="At least 25 qualified, pre-tagged completed trades required";
  if(m.count>=25&&m.mean_r<-.1&&m.recent_mean_r<0&&
    m.profit_factor!==null&&m.profit_factor<.85){
   status="PAUSE_PAPER_RESEARCH";multiplier=0;
   reason="Persistent negative gross expectancy";
  }else if(m.count>=30&&m.last_10_mean_r<-.2&&m.recent_mean_r<0){
   status="PAUSE_PAPER_RESEARCH_DRIFT";multiplier=0;
   reason="Recent performance deterioration despite earlier results";
  }else if(m.count>=40&&m.active_days>=10&&m.lower_confidence_r!==null&&
   m.lower_confidence_r>.03&&m.early_mean_r>0&&m.recent_mean_r>0&&
   m.decayed_expectancy_r>0&&m.profit_factor!==null&&m.profit_factor>1.3&&
   (m.largest_win_share??1)<.5){
   status="BOOST_PAPER_RESEARCH_2X";multiplier=2;
   reason="Chronological forward evidence across days, positive lower confidence bound and recent stability";
  }else if(m.count>=25){
   status="WATCH_FORWARD";reason="Evidence is insufficient for a boost or a pause";
  }
  strategy_results.push({strategy_id:strategy,status,
   relative_research_multiplier:multiplier,metrics:m,reason});
 }
 return {quality,strategy_results,orders_enabled:false,capital_risk_multiplier:1,
  version:"adaptive-selector-gross-v3",
  score_basis:"BROKER_PROFIT_ONLY_NO_ESTIMATED_COSTS",
  note:"2X applies ONLY to paper research frequency/priority; never to position size. Gross research scores are not broker net earnings."};
}
function scheduleResearch(backtest,forward){
 const findings=Array.isArray(backtest?.strategies)?backtest.strategies:[];
 const fw=new Map((forward?.strategy_results||[]).map(x=>[x.strategy_id,x]));
 const excluded=[],candidates=[];
 for(const item of findings){
  if(item.status!=="PAPER_CANDIDATE"){
   excluded.push({strategy_id:item.strategy_id,status:item.status});continue;
  }
  const f=fw.get(item.strategy_id),mult=f?.relative_research_multiplier??1;
  if(mult===0){
   excluded.push({strategy_id:item.strategy_id,status:f.status});continue;
  }
  const base=Math.max(.001,Number(item.oos?.lower_confidence_expectancy_r)||.001);
  candidates.push({strategy_id:item.strategy_id,family:item.family||"unknown",
   unscaled_weight:base*mult,forward_status:f?.status||"NOT_TAGGED",
   reason:f?.reason||"Forward trial not available"});
 }
 const total=sum(candidates.map(x=>x.unscaled_weight));
 let weights=candidates.map(x=>total>0?x.unscaled_weight/total:0);
 // Avoid putting almost all paper experiments in one strategy family.
 const families=new Set(candidates.map(x=>x.family));
 if(families.size>1){
  for(let pass=0;pass<12;pass++){
   const familyTotals=new Map();
   candidates.forEach((c,i)=>familyTotals.set(c.family,(familyTotals.get(c.family)||0)+weights[i]));
   const heavy=[...familyTotals].find(([,v])=>v>.6500001);
   if(!heavy)break;
   const [family,current]=heavy;
   const excess=current-.65,other=sum(weights.filter((_,i)=>candidates[i].family!==family));
   if(other<=0)break;
   weights=weights.map((w,i)=>candidates[i].family===family?w*.65/current:w+excess*w/other);
  }
 }
 const allocations=candidates.map((c,i)=>({strategy_id:c.strategy_id,
  weight:weights[i],forward_status:c.forward_status,reason:c.reason}))
  .sort((a,b)=>b.weight-a.weight);
 return {mode:"PAPER_RESEARCH_ONLY",execution_enabled:false,
  allocations,excluded,capital_risk_multiplier:1,
  note:"Adaptive 2X is research priority, not a lot multiplier; family diversification cap 65% when possible."};
}
module.exports={assessForward,scheduleResearch,ALLOWED,expectancy};
