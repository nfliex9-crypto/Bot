"use strict";
/*
 * Sentinel Brain API — private, read-only MT5 intelligence pipeline.
 * SSO protected: trades + candles -> Neon -> chronological OOS research.
 * Absolutely no order endpoints; no live mode, no synthetic data.
 */
const crypto=require("node:crypto");
const {neon}=require("@neondatabase/serverless");
const brain=require("../brain/engine.js");
const selector=require("../brain/selector.js");
const API="https://api.tickerall.com";
const TF=new Set(["M5","M15","H1","H4","D1"]);
const MAX_HOURS={M5:720,M15:2200,H1:8760,H4:17520,D1:43800};
const codeMessage=e=>String(e?.message||"ERROR").slice(0,90);
function protect(req){
 if(process.env.SENTINEL_VERCEL_SSO!=="enabled")return false;
 const host=String(req.headers.host||"").toLowerCase();
 if(!/^sentinel-mt5-console(?:-[a-z0-9-]+)?\.vercel\.app$/.test(host))return false;
 if(req.method==="POST"){
  const origin=String(req.headers.origin||"");
  if(origin&&origin!=="https://"+host)return false;
  if(req.headers["sec-fetch-site"]==="cross-site")return false;
 }
 return true;
}
function reply(res,status,body){
 res.setHeader("Cache-Control","private, no-store, max-age=0");
 res.setHeader("X-Content-Type-Options","nosniff");
 res.setHeader("Cross-Origin-Resource-Policy","same-origin");
 return res.status(status).json(body);
}
function database(){if(!process.env.DATABASE_URL)throw Error("DB_UNAVAILABLE");return neon(process.env.DATABASE_URL)}
function decrypt(b){
 const key=process.env.MT5_CLOUD_ENCRYPTION_KEY;
 if(!/^[0-9a-f]{64}$/i.test(key||""))throw Error("BRIDGE_NOT_CONFIGURED");
 const parts=String(b||"").split(".");
 if(parts.length!==3)throw Error("INVALID_SECRET_FORMAT");
 const dec=crypto.createDecipheriv("aes-256-gcm",Buffer.from(key,"hex"),Buffer.from(parts[0],"base64"));
 dec.setAuthTag(Buffer.from(parts[1],"base64"));
 return Buffer.concat([dec.update(Buffer.from(parts[2],"base64")),dec.final()]).toString("utf8");
}
async function access(sql){
 const keys=await sql`SELECT cipher_value FROM sentinel_mt5_cloud_config WHERE config_key='tickerall_api_token' LIMIT 1`;
 if(keys.length!==1)throw Error("TICKERALL_NOT_CONNECTED");
 return decrypt(keys[0].cipher_value);
}
function accountId(v){
 const id=String(v||"");
 if(!/^[A-Za-z0-9_-]{3,128}$/.test(id))throw Error("INVALID_ACCOUNT_ID");
 return id;
}
function symbolName(v){
 const s=String(v||"").trim();
 if(!/^[A-Za-z0-9._#-]{2,24}$/.test(s))throw Error("INVALID_SYMBOL");
 return s;
}
async function provider(path,token){
 if(!/^\/v1\/accounts(?:\/[A-Za-z0-9_-]+(?:\/(?:history|candles|symbols))?)?(?:\?[A-Za-z0-9&%._=:+-]*)?$/.test(path))
  throw Error("UNSAFE_PROVIDER_PATH");
 let resp;
 try{
  resp=await fetch(API+path,{method:"GET",
   headers:{Authorization:"Bearer "+token,Accept:"application/json"},
   signal:AbortSignal.timeout(12000),redirect:"error",cache:"no-store"});
 }catch(_){throw Error("TICKERALL_UNREACHABLE")}
 let data;
 try{data=await resp.json()}catch(_){data=null}
 if(!resp.ok){
  if(resp.status===409)throw Error("BROKER_SESSION_COLD");
  if(resp.status===401||resp.status===403)throw Error("TICKERALL_AUTH_FAILED");
  if(resp.status===429)throw Error("TICKERALL_RATE_LIMIT");
  throw Error("TICKERALL_HTTP_"+resp.status);
 }
 return data;
}
async function verifyDemo(token,id){
 const accounts=await provider("/v1/accounts",token);
 const list=Array.isArray(accounts)?accounts:(accounts?.accounts||[]);
 const a=list.find(x=>x.id===id&&x.broker==="mt5"&&x.isDemo===true);
 if(!a)throw Error("DEMO_ACCOUNT_REQUIRED");
 if(!a.hot)throw Error("BROKER_SESSION_COLD");
 return a;
}
async function tagOpenPosition(sql,id,token,body){
 await verifyDemo(token,id);
 const ticket=String(body.ticket||"").trim(),strategyId=String(body.strategyId||"").trim();
 const riskAmount=Number(body.riskAmount);
 if(!/^[0-9]{1,24}$/.test(ticket)||!selector.ALLOWED.has(strategyId)||
   !Number.isFinite(riskAmount)||riskAmount<=0||riskAmount>1000000)
   throw Error("INVALID_PRETRADE_TAG");
 // Check the broker position is actually OPEN *now*, in a DEMO terminal.
 const snapshot=await provider("/v1/accounts/"+id,token);
 if(snapshot?.isDemo!==true||snapshot?.account?.accountType!=="demo"||snapshot?.status!=="online")
   throw Error("DEMO_ACCOUNT_REQUIRED");
 const p=(snapshot.positions||[]).find(x=>String(x.ticket)===ticket);
 if(!p)throw Error("POSITION_NOT_OPEN");
 const opened=Date.parse(String(p.openTime||""));
 const age=Date.now()-opened;
 // Retroactive labelling of a known winner would contaminate the learning set.
 if(!Number.isFinite(age)||age< -20000||age>120000)
   throw Error("TAG_WINDOW_EXPIRED");
 const symbol=symbolName(p.symbol);
 const rows=await sql`INSERT INTO sentinel_brain_order_tags
  (account_id,ticket,symbol,strategy_id,risk_amount)
  VALUES(${id},${ticket},${symbol},${strategyId},${riskAmount})
  ON CONFLICT(account_id,ticket) DO NOTHING RETURNING account_id,ticket,strategy_id,recorded_at`;
 return {tagged:rows.length===1,strategy_id:rows[0]?.strategy_id||null,
  reason:rows.length?"RECORDED_BEFORE_CLOSE":"ALREADY_TAGGED",
  order_submitted:false};
}
async function tradeSync(sql,id,token){
 await verifyDemo(token,id);
 const r=await provider("/v1/accounts/"+id+"/history?limit=5000&waitMs=0",token);
 const raw=Array.isArray(r)?r:(r?.trades||[]);
 const rows=raw.map(brain.normalizeClosedTrade).filter(Boolean);
 if(rows.length){
  // Bulk insert, immutable broker ticket/time identity. Never invent strategy IDs.
  // Provider swap/commission may be placeholders, and are not "verified net P&L".
  const json=JSON.stringify(rows.map(x=>({
   ticket:x.ticket,close_time:x.closeTime,open_time:x.openTime,
   symbol:x.symbol,side:x.side,volume:x.volume,open_price:x.openPrice,
   close_price:x.closePrice,broker_profit:x.brokerProfit,swap:x.swap,
   commission:x.commission,complete:x.complete
  })));
  await sql`INSERT INTO sentinel_brain_trades
   (account_id,ticket,close_time,open_time,symbol,side,volume,open_price,close_price,broker_profit,swap,commission,complete)
   SELECT ${id},r.ticket,r.close_time,r.open_time,r.symbol,r.side,r.volume,r.open_price,
     r.close_price,r.broker_profit,r.swap,r.commission,r.complete
   FROM jsonb_to_recordset(${json}::jsonb) AS r(
     ticket text,close_time timestamptz,open_time timestamptz,symbol text,side text,
     volume numeric,open_price numeric,close_price numeric,broker_profit numeric,
     swap numeric,commission numeric,complete boolean)
   ON CONFLICT(account_id,ticket,close_time) DO UPDATE SET
     broker_profit=EXCLUDED.broker_profit,complete=EXCLUDED.complete,
     volume=EXCLUDED.volume,swap=EXCLUDED.swap,commission=EXCLUDED.commission,
     imported_at=NOW()`;
 }
 // Attribute only tickets recorded while positions were still open, before close.
 // No retroactive strategy labels based on whether a trade won.
 await sql`UPDATE sentinel_brain_trades AS t SET
   strategy_id=x.strategy_id,risk_amount=x.risk_amount,tagged_at=x.recorded_at,
   attribution='open_position_ledger'
   FROM sentinel_brain_order_tags AS x
   WHERE t.account_id=${id} AND x.account_id=t.account_id AND x.ticket=t.ticket
     AND x.symbol=t.symbol AND x.recorded_at<t.close_time
     AND t.complete=true AND t.strategy_id IS NULL`;
 const stored=await sql`SELECT ticket,close_time,broker_profit,complete,strategy_id
   FROM sentinel_brain_trades WHERE account_id=${id}
   ORDER BY close_time ASC LIMIT 5000`;
 const perf=brain.reviewRealTrades(stored.map(x=>({
   complete:x.complete,brokerProfit:x.broker_profit,strategyId:x.strategy_id
 })));
 return {source:"TickerAll MT5 Demo",received:raw.length,normalized:rows.length,stored:stored.length,
  ...perf,fee_data_complete:false,attribution_available:perf.completed_records>perf.unattributed_records};
}
async function candlesSync(sql,id,token,request){
 await verifyDemo(token,id);
 const symbol=symbolName(request.symbol),timeframe=String(request.timeframe||"M15").toUpperCase();
 if(!TF.has(timeframe))throw Error("INVALID_TIMEFRAME");
 const hours=Number(request.hours??720);
 if(!Number.isInteger(hours)||hours<24||hours>MAX_HOURS[timeframe])throw Error("INVALID_HISTORY_WINDOW");
 const query=new URLSearchParams({symbol,timeframe,hours:String(hours)});
 const output=await provider("/v1/accounts/"+id+"/candles?"+query.toString(),token);
 const raw=Array.isArray(output?.candles)?output.candles:[];
 const {bars,quality}=brain.normalizeCandles(raw);
 // Conservative budget for a single serverless run; no hidden request retries.
 const capped=bars.length>10000?bars.slice(-10000):bars;
 if(capped.length){
  const json=JSON.stringify(capped.map(b=>({
   bar_time:new Date(b.timestamp).toISOString(),open:b.open,high:b.high,
   low:b.low,close:b.close,spread:b.spread,tick_volume:b.tickVolume
  })));
  await sql`INSERT INTO sentinel_brain_candles
   (account_id,symbol,timeframe,bar_time,open,high,low,close,spread,tick_volume)
   SELECT ${id},${symbol},${timeframe},r.bar_time,r.open,r.high,r.low,r.close,
     r.spread,r.tick_volume FROM jsonb_to_recordset(${json}::jsonb)
     AS r(bar_time timestamptz,open numeric,high numeric,low numeric,
       close numeric,spread numeric,tick_volume numeric)
   ON CONFLICT(account_id,symbol,timeframe,bar_time) DO UPDATE SET
     open=EXCLUDED.open,high=EXCLUDED.high,low=EXCLUDED.low,
     close=EXCLUDED.close,spread=EXCLUDED.spread,
     tick_volume=EXCLUDED.tick_volume,fetched_at=NOW()`;
 }
 const truncated=output?.truncated===true||bars.length>10000;
 const coverage=String(output?.coverage||"unknown").slice(0,25);
 const stopReason=String(output?.stopReason||"").slice(0,60);
 await sql`INSERT INTO sentinel_brain_imports
   (account_id,symbol,timeframe,requested_hours,provider_count,coverage,truncated,stop_reason,imported_at)
   VALUES(${id},${symbol},${timeframe},${hours},${capped.length},${coverage},${truncated},
    ${stopReason},NOW()) ON CONFLICT(account_id,symbol,timeframe) DO UPDATE SET
    requested_hours=EXCLUDED.requested_hours,provider_count=EXCLUDED.provider_count,
    coverage=EXCLUDED.coverage,truncated=EXCLUDED.truncated,
    stop_reason=EXCLUDED.stop_reason,imported_at=NOW()`;
 return {symbol,timeframe,requested_hours:hours,received:raw.length,accepted:capped.length,
  coverage,truncated,stop_reason:stopReason,quality,
  note:"Incomplete or truncated history cannot promote any candidate."};
}
async function evaluation(sql,id,req){
 const symbol=symbolName(req.symbol),timeframe=String(req.timeframe||"M15").toUpperCase();
 if(!TF.has(timeframe))throw Error("INVALID_TIMEFRAME");
 const [importRows,barRows,tradeRows,taggedRows]=await Promise.all([
  sql`SELECT coverage,truncated,stop_reason,provider_count
    FROM sentinel_brain_imports WHERE account_id=${id} AND symbol=${symbol} AND timeframe=${timeframe}`,
  sql`SELECT bar_time,open,high,low,close,spread,tick_volume FROM sentinel_brain_candles
    WHERE account_id=${id} AND symbol=${symbol} AND timeframe=${timeframe}
    ORDER BY bar_time DESC LIMIT 10000`,
  sql`SELECT COUNT(*)::int AS count FROM sentinel_brain_trades WHERE account_id=${id} AND complete=true`,
  sql`SELECT close_time,broker_profit,complete,strategy_id,risk_amount,tagged_at
      FROM sentinel_brain_trades WHERE account_id=${id} AND strategy_id IS NOT NULL
      ORDER BY close_time DESC LIMIT 2000`
 ]);
 const meta=importRows[0];
 const latestRows=meta?barRows.slice(0,Math.min(barRows.length,Math.max(0,Number(meta.provider_count)||0))):[];
 if(!meta||latestRows.length<320)throw Error("IMPORT_HISTORY_FIRST");
 // Research only the last provider-confirmed window; never mix in older unverified imports.
 const bars=latestRows.reverse().map(b=>({
  timestamp:new Date(b.bar_time).getTime(),open:Number(b.open),high:Number(b.high),
  low:Number(b.low),close:Number(b.close),
  spread:b.spread===null?null:Number(b.spread),
  tickVolume:b.tick_volume===null?null:Number(b.tick_volume)
 }));
 const results=brain.research(bars,{coverage:meta.coverage,
  truncated:meta.truncated||Number(meta.provider_count)>10000,stopReason:meta.stop_reason});
 const forward=selector.assessForward(taggedRows.map(t=>({
    closeTime:t.close_time,brokerProfit:t.broker_profit,complete:t.complete,
    strategyId:t.strategy_id,riskAmount:t.risk_amount,taggedAt:t.tagged_at
 })));
 results.forward_quality=forward.quality;
 results.paper_schedule=selector.scheduleResearch(results,forward);
 const runId=crypto.randomUUID(),quality=JSON.stringify(results.quality),analysis=JSON.stringify(results);
 await sql`INSERT INTO sentinel_brain_runs
 (id,account_id,symbol,timeframe,candles_used,historical_trades_seen,coverage,data_quality,analysis)
 VALUES(${runId},${id},${symbol},${timeframe},${bars.length},
    ${Number(tradeRows[0]?.count||0)},${meta.coverage},${quality}::jsonb,${analysis}::jsonb)`;
 return {run_id:runId,symbol,timeframe,evidence:results,mode:"RESEARCH_ONLY",orders_executed:0};
}
async function status(sql){
 const [trades,bars,runs,imports,tagged]=await Promise.all([
  sql`SELECT account_id,COUNT(*)::int AS all_count,
    COUNT(*) FILTER(WHERE complete)::int AS completed,
    COUNT(*) FILTER(WHERE complete AND strategy_id IS NOT NULL)::int AS attributed,
    COUNT(*) FILTER(WHERE complete AND broker_profit>0)::int AS wins,
    SUM(broker_profit) FILTER(WHERE complete)::float AS recorded_profit,
    MAX(close_time) FILTER(WHERE complete) AS last_closed_trade
    FROM sentinel_brain_trades GROUP BY account_id ORDER BY MAX(close_time) DESC LIMIT 15`,
  sql`SELECT COUNT(*)::int AS count FROM sentinel_brain_candles`,
  sql`SELECT id,account_id,symbol,timeframe,candles_used,coverage,analysis,created_at
    FROM sentinel_brain_runs ORDER BY created_at DESC LIMIT 6`,
  sql`SELECT account_id,symbol,timeframe,requested_hours,provider_count,coverage,truncated,
    imported_at FROM sentinel_brain_imports ORDER BY imported_at DESC LIMIT 15`,
  sql`SELECT account_id,close_time,broker_profit,complete,strategy_id,risk_amount,tagged_at
    FROM sentinel_brain_trades WHERE strategy_id IS NOT NULL ORDER BY close_time DESC LIMIT 2000`
 ]);
 const grouped=new Map();
 for(const t of tagged){
   const group=grouped.get(t.account_id)||[];
   group.push({closeTime:t.close_time,brokerProfit:t.broker_profit,
     complete:t.complete,strategyId:t.strategy_id,riskAmount:t.risk_amount,
     taggedAt:t.tagged_at});
   grouped.set(t.account_id,group);
 }
 const forward_by_account={};
 for(const [id,group] of grouped)forward_by_account[id]=selector.assessForward(group);
 const accountRows=trades.map(x=>({account_id:x.account_id,
    real_trades:Number(x.all_count||0),completed_trades:Number(x.completed||0),
    attributed_trades:Number(x.attributed||0),wins:Number(x.wins||0),
    recorded_broker_profit:x.recorded_profit===null?null:Number(x.recorded_profit),
    last_closed_trade:x.last_closed_trade,fees_verified:false}));
 return {version:brain.VERSION,
  real_trades:accountRows.reduce((n,a)=>n+a.real_trades,0),
  completed_trades:accountRows.reduce((n,a)=>n+a.completed_trades,0),
  attributed_trades:accountRows.reduce((n,a)=>n+a.attributed_trades,0),
  accounts:accountRows,forward_by_account,
  candles:Number(bars[0]?.count||0),
  runs:runs.map(x=>({id:x.id,account_id:x.account_id,symbol:x.symbol,timeframe:x.timeframe,
   candles:x.candles_used,date:x.created_at,portfolio:x.analysis?.portfolio,
   paper_schedule:x.analysis?.paper_schedule,forward_quality:x.analysis?.forward_quality,
   strategies:x.analysis?.strategies?.map(s=>({
    id:s.strategy_id,status:s.status,trades:s.oos.trades,expectancy_r:s.oos.expectancy_r,
    stress_expectancy_r:s.double_costs.expectancy_r,reason:s.reason
   }))||[]})),
  imports:imports,execution_enabled:false,worker_running:false};
}
module.exports=async(req,res)=>{
 const action=String(req.query?.action||"");
 const routes={status:"GET",symbols:"POST",tagPosition:"POST",syncTrades:"POST",syncCandles:"POST",evaluate:"POST"};
 if(!Object.hasOwn(routes,action))return reply(res,404,{ok:false,error:"UNKNOWN_ACTION"});
 if(req.method!==routes[action])return reply(res,405,{ok:false,error:"INVALID_METHOD"});
 if(!protect(req))return reply(res,403,{ok:false,error:"PROTECTED_DASHBOARD_REQUIRED"});
 if(JSON.stringify(req.body||{}).length>4000)return reply(res,413,{ok:false,error:"BODY_TOO_LARGE"});
 let sql;
 try{sql=database()}catch(_){return reply(res,503,{ok:false,error:"DB_UNAVAILABLE"})}
 try{
  if(action==="status")return reply(res,200,{ok:true,data:await status(sql)});
  const id=accountId(req.body?.accountId);
  if(action==="evaluate"){
   // Evaluation does NOT connect brokers, place trades, or change strategy risk.
   return reply(res,200,{ok:true,data:await evaluation(sql,id,req.body||{})});
  }
  const token=await access(sql);
  if(action==="symbols"){
   await verifyDemo(token,id);
   const list=await provider("/v1/accounts/"+id+"/symbols",token);
   return reply(res,200,{ok:true,data:{symbols:Array.isArray(list?.symbols)?list.symbols.slice(0,600):[]}});}
  if(action==="tagPosition")return reply(res,200,{ok:true,data:await tagOpenPosition(sql,id,token,req.body||{})});
  if(action==="syncTrades")return reply(res,200,{ok:true,data:await tradeSync(sql,id,token)});
  if(action==="syncCandles")return reply(res,200,{ok:true,data:await candlesSync(sql,id,token,req.body||{})});
  return reply(res,404,{ok:false,error:"UNKNOWN_ACTION"});
 }catch(e){
  const code=codeMessage(e);
  const known=new Set(["DEMO_ACCOUNT_REQUIRED","BROKER_SESSION_COLD","TICKERALL_RATE_LIMIT",
   "TICKERALL_NOT_CONNECTED","TICKERALL_AUTH_FAILED","TICKERALL_UNREACHABLE",
   "INVALID_SYMBOL","INVALID_TIMEFRAME","INVALID_HISTORY_WINDOW","IMPORT_HISTORY_FIRST",
   "INVALID_ACCOUNT_ID","INVALID_PRETRADE_TAG","POSITION_NOT_OPEN","TAG_WINDOW_EXPIRED"]);
  if(known.has(code))return reply(res,422,{ok:false,error:code});
  // Do not leak database details, encrypted tokens, provider bodies, or trade history.
  console.error("sentinel_brain_failure",code.replace(/[\r\n]/g,"").slice(0,85));
  return reply(res,503,{ok:false,error:"RESEARCH_WORKER_UNAVAILABLE"});
 }
};
