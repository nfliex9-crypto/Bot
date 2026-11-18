"use strict";
/* SSO-protected, read-only status endpoint for the independent MT5 DEMO trader.
   Trading stays in Windows MT5; there are no order, stop, size, or kill controls.
 */
const {neon}=require("@neondatabase/serverless");
function reply(res,status,body){
 res.setHeader("Cache-Control","private,no-store");
 res.setHeader("X-Content-Type-Options","nosniff");
 res.setHeader("Cross-Origin-Resource-Policy","same-origin");
 return res.status(status).json(body);
}
function protectedOwner(req){
 return process.env.SENTINEL_VERCEL_SSO==="enabled"&&
  /^sentinel-mt5-console(?:-[a-z0-9-]+)?\.vercel\.app$/.test(String(req.headers.host||"").toLowerCase());
}
module.exports=async(req,res)=>{
 if(req.method!=="GET")return reply(res,405,{ok:false,error:"READ_ONLY_ENDPOINT"});
 if(!protectedOwner(req))return reply(res,403,{ok:false,error:"PROTECTED_DASHBOARD_REQUIRED"});
 if(!process.env.DATABASE_URL)return reply(res,503,{ok:false,error:"DATABASE_NOT_CONFIGURED"});
 try{
  const sql=neon(process.env.DATABASE_URL);
  const records=await sql`SELECT s.agent_id,s.updated_at,s.snapshot,s.account_last4,
    a.last_seen_at,a.connection_state,a.trade_mode,a.bot_state
    FROM sentinel_independent_trader_status s JOIN sentinel_mt5_agents a USING(agent_id)
    ORDER BY s.updated_at DESC LIMIT 10`;
  const now=Date.now();
  const entries=records.map(r=>{
   const updated=new Date(r.updated_at).getTime(),seen=new Date(r.last_seen_at).getTime();
   const fresh=Number.isFinite(updated)&&Number.isFinite(seen)&&
    now-updated>=0&&now-updated<90000&&now-seen>=0&&now-seen<90000&&
    r.trade_mode==="demo"&&r.connection_state==="connected";
   return {agent_id:r.agent_id,updated_at:r.updated_at,account_last4:r.account_last4,
     status:fresh?"DEMO_TELEMETRY_FRESH":"OFFLINE_OR_STALE",
     mode:r.snapshot?.mode||"unknown",execution_armed:fresh&&r.snapshot?.execution_armed===true,
     symbols:fresh?(r.snapshot?.symbols||[]):[],
     broker_fill_proven:false,
     note:"Device state only. Broker execution requires independent order/deal reconciliation."};
  });
  return reply(res,200,{ok:true,mode:"INDEPENDENT_DEMO_TRADER_STATUS_ONLY",
   trader:entries,generated_at:new Date().toISOString(),
   remote_order_endpoints_enabled:false});
 }catch(err){
  console.error("sentinel_trader_status_unavailable",String(err?.code||"DB_ERROR").slice(0,50));
  return reply(res,503,{ok:false,error:"TRADER_TELEMETRY_NOT_DEPLOYED_OR_UNAVAILABLE"});
 }
};
