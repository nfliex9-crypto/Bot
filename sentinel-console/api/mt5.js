"use strict";
/**
 * Sentinel MT5 bridge: secure one-time pairing + heartbeat monitoring.
 * Does NOT accept trading orders, broker passwords, or remote shell commands.
 */
const crypto = require("node:crypto");
const {neon}=require("@neondatabase/serverless");
function answer(res,status,obj){res.setHeader("Cache-Control","no-store");res.setHeader("X-Content-Type-Options","nosniff");return res.status(status).json(obj)}
function constEqual(a,b){if(typeof a!=="string"||typeof b!=="string")return false;const x=Buffer.from(a);const y=Buffer.from(b);return x.length===y.length&&crypto.timingSafeEqual(x,y)}
function sha(x){return crypto.createHash("sha256").update(x).digest("hex")}
const hexUUID=()=>crypto.randomUUID();
function server(){if(!process.env.DATABASE_URL)throw Error("DATABASE_URL missing");return neon(process.env.DATABASE_URL)}
function owner(req){return constEqual(req.headers["x-console-key"],process.env.DASHBOARD_ACCESS_KEY)}
function tokenString(req){const x=req.headers["x-mt5-agent-token"];return typeof x==="string"&&/^[0-9a-f]{64}$/.test(x)?x:null}
function normalizeCode(input){return String(input||"").toUpperCase().replace(/[^A-Z2-7]/g,"")}
function code(){const alphabet="ABCDEFGHJKLMNPQRSTUVWXYZ23456789";const b=crypto.randomBytes(20);return [...b].map(n=>alphabet[n%alphabet.length]).join("")}
const shorten=(x,max=100)=>String(x||"").slice(0,max);
module.exports=async(req,res)=>{
 res.setHeader("Cache-Control","private, no-store, max-age=0");
 const action=String(req.query.action||"");
 if(!["GET","POST"].includes(req.method))return answer(res,405,{ok:false,error:"METHOD_NOT_ALLOWED"});
 if(req.method==="POST"&&Buffer.byteLength(JSON.stringify(req.body||{}))>8192)return answer(res,413,{ok:false,error:"PAYLOAD_TOO_LARGE"});
 const ownerOps=["status","setup","revoke"];
 const agentOps=["claim","heartbeat"];
 if(![...ownerOps,...agentOps].includes(action))return answer(res,404,{ok:false,error:"UNKNOWN_ACTION"});
 if(ownerOps.includes(action)&&!owner(req))return answer(res,401,{ok:false,error:"UNAUTHORIZED"});
 if((action==="status"&&req.method!=="GET")||(action!=="status"&&req.method!=="POST"))return answer(res,405,{ok:false,error:"METHOD_NOT_ALLOWED"});
 let sql;
 try{sql=server()}catch(_){return answer(res,503,{ok:false,error:"BRIDGE_DB_NOT_CONFIGURED"})}
 try{
  if(action==="status"){
    const rows=await sql`SELECT agent_id, agent_name, created_at, last_seen_at,last_ok_at,account_last4,
 broker_server, account_currency, balance, equity,open_positions,terminal_version,
 trade_mode,connection_state,bot_state,last_error,heartbeat_count,
 CASE WHEN last_seen_at IS NULL THEN NULL ELSE FLOOR(EXTRACT(EPOCH FROM (NOW()-last_seen_at)))::INT END AS age_seconds
 FROM sentinel_mt5_agents ORDER BY created_at DESC LIMIT 15`;
    const devices=rows.map(r=>({...r,connected:r.age_seconds!==null&&r.age_seconds<90&&r.trade_mode==="demo"&&r.connection_state==="connected",stale:r.age_seconds===null||r.age_seconds>=90}));
    return answer(res,200,{ok:true,devices,generated_at:new Date().toISOString(),online_count:devices.filter(d=>d.connected).length});
  }
  if(action==="setup"){
    const created=code();
    const grouped=created.match(/.{1,5}/g).join("-");
    const idhash=sha(created);
    await sql`INSERT INTO sentinel_mt5_pairings(code_hash,expires_at) VALUES (${idhash},NOW()+INTERVAL '15 minutes')`;
    return answer(res,201,{ok:true,pairing_code:grouped,expires_in_seconds:900,endpoint:"https://sentinel-mt5-bridge.vercel.app"});
  }
  if(action==="claim"){
    const normalized=normalizeCode(req.body?.code);
    if(normalized.length!==20)return answer(res,400,{ok:false,error:"INVALID_CODE_FORMAT"});
    const codeHash=sha(normalized);
    const claimed=await sql`UPDATE sentinel_mt5_pairings SET claimed_at=NOW()
      WHERE code_hash=${codeHash} AND claimed_at IS NULL AND expires_at>NOW() RETURNING code_hash`;
    if(claimed.length!==1)return answer(res,401,{ok:false,error:"PAIRING_EXPIRED_OR_INVALID"});
    const agentId=hexUUID(),token=crypto.randomBytes(32).toString("hex");
    const name=shorten(req.body?.agent_name||"Windows MT5 Agent",80);
    await sql`INSERT INTO sentinel_mt5_agents(agent_id,token_hash,agent_name)
      VALUES (${agentId},${sha(token)},${name})`;
    await sql`UPDATE sentinel_mt5_pairings SET agent_id=${agentId} WHERE code_hash=${codeHash}`;
    return answer(res,201,{ok:true,agent_id:agentId,agent_token:token,heartbeat_interval_seconds:20});
  }
  if(action==="revoke"){
    const agentId=String(req.body?.agent_id||"");
    if(!/^[0-9a-f-]{36}$/i.test(agentId))return answer(res,400,{ok:false,error:"BAD_AGENT_ID"});
    const updated=await sql`UPDATE sentinel_mt5_agents SET token_hash='REVOKED-'||${crypto.randomUUID()}, connection_state='revoked', last_error='Agent revoked by console' WHERE agent_id=${agentId} RETURNING agent_id`;
    return answer(res,200,{ok:true,revoked:updated.length===1});
  }
  if(action==="heartbeat"){
    const token=tokenString(req),agentId=String(req.headers["x-mt5-agent-id"]||"");
    if(!token||!/^[0-9a-f-]{36}$/i.test(agentId))return answer(res,401,{ok:false,error:"BAD_DEVICE_AUTH"});
    const h=sha(token);
    const body=req.body||{};
    const mode=body.trade_mode==="demo"?"demo":"unknown";
    const connected=mode==="demo"&&body.connection_state==="connected";
    const state=connected?"connected":"disconnected";
    const last4=/^[0-9]{1,4}$/.test(String(body.account_last4||""))?String(body.account_last4):null;
    const balance=Number(body.balance),equity=Number(body.equity);
    const count=Number(body.open_positions);
    const rows=await sql`UPDATE sentinel_mt5_agents SET
      last_seen_at=NOW(),last_ok_at=CASE WHEN ${connected} THEN NOW() ELSE last_ok_at END,
      account_last4=${last4},broker_server=${shorten(body.broker_server,80)},
      account_currency=${shorten(body.account_currency,8)},
      balance=${Number.isFinite(balance)&&balance>=0?balance:null},equity=${Number.isFinite(equity)&&equity>=0?equity:null},
      open_positions=${Number.isSafeInteger(count)&&count>=0&&count<10000?count:null},
      terminal_version=${shorten(body.terminal_version,40)},trade_mode=${mode},
      connection_state=${state},
      bot_state=${["running","restarting","stopped","unconfigured","failed"].includes(body.bot_state)?body.bot_state:"unconfigured"},
      last_error=${connected?null:shorten(body.last_error,300)},
      heartbeat_count=heartbeat_count+1
      WHERE agent_id=${agentId} AND token_hash=${h} AND connection_state <> 'revoked'
      RETURNING agent_id`;
    if(rows.length!==1)return answer(res,401,{ok:false,error:"DEVICE_REVOKED_OR_NOT_FOUND"});
    return answer(res,200,{ok:true,server_time:new Date().toISOString()});
  }
 }catch(err){
   // No SQL/broker details leaked to public callers.
   console.error("mt5_bridge_error",String(err?.message||err).slice(0,160));
   return answer(res,503,{ok:false,error:"TEMPORARY_BRIDGE_ERROR"});
 }
};
