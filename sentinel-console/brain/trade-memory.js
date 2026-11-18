"use strict";
/*
 * Broker Trade Memory v1: EVERY completed broker trade, including untagged
 * trades, contributes to descriptive market/session/side statistics.
 * This is not strategy attribution or permission to place orders.
 */
const numeric=x=>{
 if(x===null||x===undefined||x===""||typeof x==="boolean")return null;
 const v=Number(x);return Number.isFinite(v)?v:null;
};
const avg=x=>x.length?x.reduce((a,b)=>a+b,0)/x.length:0;
const sum=x=>x.reduce((a,b)=>a+b,0);
function session(ts){
 const h=new Date(ts).getUTCHours();
 if(h>=7&&h<13)return "london";
 if(h>=13&&h<21)return "new_york";
 if(h>=0&&h<7)return "asia";
 return "late";
}
function summary(trades){
 const vals=trades.map(x=>x.profit);
 const wins=vals.filter(x=>x>0),losses=vals.filter(x=>x<0);
 let total=0,peak=0,drawdown=0;
 for(const x of vals){total+=x;peak=Math.max(peak,total);drawdown=Math.max(drawdown,peak-total)}
 const recent=vals.slice(-Math.min(10,vals.length));
 const early=vals.slice(0,Math.floor(vals.length/2));
 const profitFactor=losses.length?sum(wins)/Math.abs(sum(losses)):null;
 let status="INSUFFICIENT",reason="Fewer than 20 completed broker trades";
 if(vals.length>=20&&avg(vals)<0&&avg(recent)<0){
  status="AVOID_PAPER_EXPERIMENTS";reason="Negative recorded P/L in full and recent samples";
 }else if(vals.length>=30&&avg(vals)>0&&avg(recent)>0&&avg(early)>0&&
   profitFactor!==null&&profitFactor>1.2){
  status="REVIEW_FOR_MORE_PAPER_TESTS";reason="Positive history, not verified strategy attribution";
 }else if(vals.length>=20){
  status="WATCH";reason="Mixed or inconclusive evidence";
 }
 return {trades:vals.length,broker_reported_profit:total,
  mean_broker_profit:avg(vals),recent_mean_broker_profit:avg(recent),
  win_rate:vals.length?wins.length/vals.length:null,profit_factor:profitFactor,
  recorded_max_drawdown:drawdown,status,reason};
}
function tradeMemory(rows){
 if(!Array.isArray(rows))throw Error("BROKER_TRADES_EXPECTED");
 const quality={records:rows.length,completed:0,skipped:0,missing_entry_time:0,
  unverified_costs:true,attribution_required_for_strategy_selection:true};
 const accepted=[];
 for(const row of rows){
  const profit=numeric(row.brokerProfit??row.broker_profit);
  const closed=new Date(row.closeTime??row.close_time).getTime();
  const opened=new Date(row.openTime??row.open_time).getTime();
  const symbol=String(row.symbol||"").trim().toUpperCase();
  if(row.complete!==true||profit===null||!Number.isFinite(closed)||
    !/^[A-Z0-9._#-]{2,24}$/.test(symbol)){quality.skipped++;continue}
  quality.completed++;
  if(!Number.isFinite(opened))quality.missing_entry_time++;
  accepted.push({profit,closed,opened:Number.isFinite(opened)?opened:null,
   symbol,side:String(row.side||"UNKNOWN").toUpperCase()});
 }
 accepted.sort((a,b)=>a.closed-b.closed);
 const bySymbol=new Map(),bySession=new Map(),bySide=new Map();
 for(const row of accepted){
  const where=row.opened??row.closed;
  for(const [map,key] of [[bySymbol,row.symbol],[bySession,session(where)],[bySide,row.side]]){
   const arr=map.get(key)||[];arr.push(row);map.set(key,arr);
  }
 }
 const serialize=map=>[...map].map(([name,group])=>({name,...summary(group)}))
  .sort((a,b)=>b.trades-a.trades);
 return {version:"broker-trade-memory-v1",quality,
  overall:summary(accepted),by_symbol:serialize(bySymbol),
  by_session:serialize(bySession),by_side:serialize(bySide),
  orders_enabled:false,
  note:"Every completed trade counts for broker-level descriptive analytics. No strategy is inferred from historical P/L; fees may be missing."};
}
module.exports={tradeMemory,summary,session};
