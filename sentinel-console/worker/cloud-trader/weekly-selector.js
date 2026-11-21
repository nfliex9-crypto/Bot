"use strict";
/**
 * Weekly review of broker-verified completed DEMO deals ONLY.
 * A reward changes candidate priority, never order size or risk.
 * A single lucky/unlucky week cannot shut off a strategy.
 * The first UTC Monday after a full week snapshots the prior week's evidence.
 */
const FAMILIES=Object.freeze(["pdf_sweep_bos","pdf_fvg_retest"]);
const DAY=86400000;
function monday(t){
 if(!Number.isSafeInteger(t))throw Error("INVALID_UTC_TIME");
 const d=new Date(t),u=Date.UTC(d.getUTCFullYear(),d.getUTCMonth(),d.getUTCDate());
 return u-((d.getUTCDay()+6)%7)*DAY;
}
function windowAt(now=Date.now()){
 const end=monday(now);
 return {weekStart:new Date(end-7*DAY).toISOString().slice(0,10),
  weekEnd:new Date(end).toISOString(),lookbackStart:new Date(end-28*DAY).toISOString()};
}
function verifyRow(row){
 if(!row||!FAMILIES.includes(row.family)||typeof row.symbol!=="string"||
   row.symbol.length<2||row.complete!==true||row.brokerVerified!==true)throw Error("UNVERIFIED_WEEKLY_TRADE");
 const gross=Number(row.profit);
 if(row.profit===null||row.profit===undefined||!Number.isFinite(gross))
   throw Error("MISSING_BROKER_PROFIT");
 const close=Date.parse(String(row.closeTime||""));
 if(!Number.isFinite(close))throw Error("INVALID_TRADE_CLOSE_TIME");
 return {...row,net:gross,scoreBasis:"BROKER_PROFIT_ONLY_GROSS",closedAt:close};
}
function stats(trades){
 const days=new Set(trades.map(x=>new Date(x.closedAt).toISOString().slice(0,10)));
 let gain=0,loss=0;
 for(const x of trades){if(x.net>0)gain+=x.net;else loss-=x.net}
 return {trades:trades.length,days:days.size,net:Number((gain-loss).toFixed(2)),
  profitFactor:loss>0?Number((gain/loss).toFixed(3)):null,
  avg:trades.length?Number(((gain-loss)/trades.length).toFixed(2)):null};
}
function evaluate(rows,{now=Date.now(),symbol}={}){
 const w=windowAt(now),start=Date.parse(w.weekStart),end=Date.parse(w.weekEnd),
   lookback=Date.parse(w.lookbackStart);
 const known=(rows||[]).map(verifyRow).filter(x=>x.symbol===symbol&&
   x.closedAt>=lookback&&x.closedAt<end);
 const profiles=FAMILIES.map(family=>{
  const all=known.filter(x=>x.family===family);
  const week=stats(all.filter(x=>x.closedAt>=start)),rolling=stats(all);
  const enough=week.trades>=6&&week.days>=2&&rolling.trades>=18&&rolling.days>=5;
  const negative=enough&&week.net<0&&rolling.net<0&&
    week.profitFactor!==null&&week.profitFactor<.85&&
    rolling.profitFactor!==null&&rolling.profitFactor<1;
  const positive=enough&&week.net>0&&rolling.net>0&&
    week.profitFactor!==null&&week.profitFactor>1.20&&
    rolling.profitFactor!==null&&rolling.profitFactor>1.30;
  return {family,symbol,week,rolling,enough,negative,positive,
   status:"COLLECTING",priority:1};
 });
 // Pause at most one objectively worst negative family for a symbol per week,
 // only if another strategy is not itself losing. Do not disable all entries.
 const eligible=profiles.filter(x=>x.negative).sort((a,b)=>a.week.net-b.week.net);
 const alternatives=profiles.filter(x=>!x.negative);
 if(eligible.length&&alternatives.length){
  eligible[0].status="PAUSED_LOSING";eligible[0].priority=0;
 }
 for(const x of profiles){
  if(x.priority===0)continue;
  if(x.positive){x.status="REWARDED_PRIORITY";x.priority=2}
  else if(x.negative)x.status="WATCH_NEGATIVE";
  else if(x.enough)x.status="ACTIVE_NEUTRAL";
  else x.status="COLLECTING";
 }
 return {weekStart:w.weekStart,weekEnd:w.weekEnd,symbol,profiles};
}
function policyFromScores(rows,symbol){
 const by=new Map((rows||[]).filter(x=>x.symbol===symbol&&FAMILIES.includes(x.family))
  .map(x=>[x.family,{priority:Number(x.priority),status:String(x.status)}]));
 return Object.fromEntries(FAMILIES.map(f=>[f,
  by.has(f)&&[0,1,2].includes(by.get(f).priority)?by.get(f).priority:1]));
}
async function ensureSnapshot(sql,accountId,symbol,now=Date.now()){
 const window=windowAt(now);
 const registered=await sql`SELECT family,status,priority FROM sentinel_cloud_strategy_weekly
 WHERE account_id=${accountId} AND symbol=${symbol}
 AND week_start=${window.weekStart}::date`;
 if(registered.length===FAMILIES.length){
  return {weekStart:window.weekStart,policies:policyFromScores(registered.map(x=>({...x,symbol})),symbol)};
 }
 const raw=await sql`SELECT symbol,family,close_time,profit
 FROM sentinel_cloud_trader_fills WHERE account_id=${accountId}
 AND close_time >= ${window.lookbackStart}::timestamptz
 AND close_time < ${window.weekEnd}::timestamptz
 AND family IN ('pdf_sweep_bos','pdf_fvg_retest')
 ORDER BY close_time ASC`;
 const approved=raw.map(x=>({symbol:x.symbol,family:x.family,closeTime:x.close_time,
  profit:x.profit,
  complete:true,brokerVerified:true}));
 const assessed=evaluate(approved,{symbol,now});
 for(const p of assessed.profiles){
  await sql`INSERT INTO sentinel_cloud_strategy_weekly
   (account_id,symbol,family,week_start,status,priority,week_trades,week_net,
    rolling_trades,rolling_net,evidence)
   VALUES(${accountId},${symbol},${p.family},${window.weekStart}::date,
    ${p.status},${p.priority},${p.week.trades},${p.week.net},
    ${p.rolling.trades},${p.rolling.net},${JSON.stringify({
     week:p.week,rolling:p.rolling,rules:"gross_broker_profit_only_rolling_28d_v2"})}::jsonb)
   ON CONFLICT (account_id,symbol,family,week_start) DO NOTHING`;
 }
 const final=await sql`SELECT family,status,priority FROM sentinel_cloud_strategy_weekly
 WHERE account_id=${accountId} AND symbol=${symbol}
 AND week_start=${window.weekStart}::date`;
 if(final.length!==FAMILIES.length)throw Error("WEEKLY_SCORE_INCOMPLETE");
 return {weekStart:window.weekStart,
  policies:policyFromScores(final.map(x=>({...x,symbol})),symbol)};
}
module.exports={FAMILIES,monday,windowAt,verifyRow,stats,evaluate,policyFromScores,ensureSnapshot};
