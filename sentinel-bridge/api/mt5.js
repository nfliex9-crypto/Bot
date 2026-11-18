"use strict";
// Public HTTPS ingress for Windows MT5 agents only. No dashboard, admin, or trading endpoints.
// Auth: one-time 20-char code (15 min) then 256-bit agent token. All writes scoped to the paired device.
const crypto=require("node:crypto");
const {normalizeUpload}=require("../native-ingest.js");
const {neon}=require("@neondatabase/serverless");
const sha=s=>crypto.createHash("sha256").update(s).digest("hex");
const respond=(res,status,body)=>{res.setHeader("Cache-Control","no-store");res.setHeader("X-Content-Type-Options","nosniff");return res.status(status).json(body)};
const shorten=(x,max=80)=>String(x||"").slice(0,max);
module.exports=async(req,res)=>{
 const action=String(req.query.action||"");
 if(req.method!=="POST"||!["claim","heartbeat","candles"].includes(action))return respond(res,404,{ok:false,error:"NOT_FOUND"});
 if(Buffer.byteLength(JSON.stringify(req.body||{}))>(action==="candles"?131072:8192))return respond(res,413,{ok:false,error:"PAYLOAD_TOO_LARGE"});
 if(!process.env.DATABASE_URL)return respond(res,503,{ok:false,error:"BRIDGE_NOT_CONFIGURED"});
 const sql=neon(process.env.DATABASE_URL);
 try{
  if(action==="claim"){
   const code=String(req.body?.code||"").toUpperCase().replace(/[^A-Z2-9]/g,"");
   if(code.length!==20)return respond(res,400,{ok:false,error:"INVALID_PAIRING_CODE"});
   const h=sha(code);
   const claimed=await sql`UPDATE sentinel_mt5_pairings SET claimed_at=NOW() WHERE code_hash=${h}
    AND claimed_at IS NULL AND expires_at>NOW() RETURNING code_hash`;
   if(claimed.length!==1)return respond(res,401,{ok:false,error:"PAIRING_EXPIRED_OR_INVALID"});
   const id=crypto.randomUUID(),token=crypto.randomBytes(32).toString("hex");
   await sql`INSERT INTO sentinel_mt5_agents(agent_id,token_hash,agent_name)
     VALUES (${id},${sha(token)},${shorten(req.body?.agent_name||"Windows MT5 Agent",80)})`;
   await sql`UPDATE sentinel_mt5_pairings SET agent_id=${id} WHERE code_hash=${h}`;
   return respond(res,201,{ok:true,agent_id:id,agent_token:token,heartbeat_interval_seconds:20});
  }
  const id=String(req.headers["x-mt5-agent-id"]||"");
  const token=req.headers["x-mt5-agent-token"];
  if(!/^[0-9a-f-]{36}$/i.test(id)||typeof token!=="string"||!/^[0-9a-f]{64}$/.test(token))
   return respond(res,401,{ok:false,error:"INVALID_AGENT_AUTH"});
  if(action==="candles"){
    // Live paired DEMO heartbeat is a prerequisite; the uploaded history itself
    // remains explicitly unverified and NEVER gains order/reward permissions.
    const active=await sql`SELECT account_last4 FROM sentinel_mt5_agents
      WHERE agent_id=${id} AND token_hash=${sha(token)} AND trade_mode='demo'
      AND connection_state='connected' AND last_seen_at>NOW()-INTERVAL '90 seconds'
      LIMIT 1`;
    if(active.length!==1)return respond(res,403,{ok:false,error:"FRESH_DEMO_HEARTBEAT_REQUIRED"});
    if(String(req.body?.account_last4||"")!==String(active[0].account_last4||""))
     return respond(res,403,{ok:false,error:"ACCOUNT_MISMATCH"});
    let upload;
    try{upload=normalizeUpload(req.body||{},{now:Date.now()})}
    catch(err){return respond(res,422,{ok:false,error:"INVALID_NATIVE_CANDLE_UPLOAD"})}
    const account="native-demo-"+id;
    const {symbol,timeframe,bars}=upload;
    const rows=JSON.stringify(bars.map(b=>({
      bar_time:b.time,open:b.open,high:b.high,low:b.low,close:b.close,
      spread:b.spread,tick_volume:b.tick_volume
    })));
    await sql`INSERT INTO sentinel_brain_candles
     (account_id,symbol,timeframe,bar_time,open,high,low,close,spread,tick_volume)
     SELECT ${account},${symbol},${timeframe},r.bar_time,r.open,r.high,r.low,r.close,
       r.spread,r.tick_volume FROM jsonb_to_recordset(${rows}::jsonb)
       AS r(bar_time timestamptz,open numeric,high numeric,low numeric,
       close numeric,spread numeric,tick_volume numeric)
     ON CONFLICT(account_id,symbol,timeframe,bar_time) DO UPDATE SET
       open=EXCLUDED.open,high=EXCLUDED.high,low=EXCLUDED.low,close=EXCLUDED.close,
       spread=EXCLUDED.spread,tick_volume=EXCLUDED.tick_volume,fetched_at=NOW()`;
    await sql`INSERT INTO sentinel_brain_imports
     (account_id,symbol,timeframe,requested_hours,provider_count,coverage,truncated,stop_reason,imported_at)
     VALUES(${account},${symbol},${timeframe},24,${bars.length},'local_unverified',true,'LOCAL_NATIVE_DEMO_EXPORT',NOW())
     ON CONFLICT(account_id,symbol,timeframe) DO UPDATE SET
       provider_count=GREATEST(sentinel_brain_imports.provider_count,EXCLUDED.provider_count),
       coverage='local_unverified',truncated=true,stop_reason='LOCAL_NATIVE_DEMO_EXPORT',
       imported_at=NOW()`;
    return respond(res,202,{ok:true,source:"LOCAL_MT5_DEMO_TERMINAL",symbol,timeframe,
      accepted:bars.length,unverified:true,orders_executed:0,
      note:"Native broker bars stored separately; not verified or eligible for order execution."});
  }
  const b=req.body||{};
  const mode=b.trade_mode==="demo"?"demo":"unknown";
  const connected=mode==="demo"&&b.connection_state==="connected";
  const last4=/^[0-9]{1,4}$/.test(String(b.account_last4||""))?String(b.account_last4):null;
  const balance=Number(b.balance),equity=Number(b.equity),positions=Number(b.open_positions);
  const rows=await sql`UPDATE sentinel_mt5_agents SET
    last_seen_at=NOW(),last_ok_at=CASE WHEN ${connected} THEN NOW() ELSE last_ok_at END,
    account_last4=${last4},broker_server=${shorten(b.broker_server,80)},
    account_currency=${shorten(b.account_currency,8)},
    balance=${Number.isFinite(balance)&&balance>=0?balance:null},
    equity=${Number.isFinite(equity)&&equity>=0?equity:null},
    open_positions=${Number.isSafeInteger(positions)&&positions>=0&&positions<10000?positions:null},
    terminal_version=${shorten(b.terminal_version,40)},trade_mode=${mode},
    connection_state=${connected?"connected":"disconnected"},
    bot_state=${["running","restarting","stopped","unconfigured","failed"].includes(b.bot_state)?b.bot_state:"unconfigured"},
    last_error=${connected?null:shorten(b.last_error,300)},
    heartbeat_count=heartbeat_count+1
    WHERE agent_id=${id} AND token_hash=${sha(token)} AND connection_state <> 'revoked'
    RETURNING agent_id`;
  if(rows.length!==1)return respond(res,401,{ok:false,error:"DEVICE_REVOKED_OR_NOT_FOUND"});
  return respond(res,200,{ok:true,server_time:new Date().toISOString()});
 }catch(err){
  console.error("mt5_ingress_error",String(err?.message||err).slice(0,160));
  return respond(res,503,{ok:false,error:"TEMPORARY_BRIDGE_ERROR"});
 }
};