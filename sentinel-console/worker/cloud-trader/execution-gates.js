"use strict";
// Sentinel V2: mandatory pre-entry ledger and just-in-time DB permission.
// Missing schema or disabled authorization blocks broker writes, not monitoring.
const c=require("./core.js");
const INTENT_COLUMNS=Object.freeze(["decision_tagged_at","risk_at_entry","risk_pct_at_entry","volume_at_entry","stop_loss_at_entry","take_profit_at_entry","decision_version","decision_snapshot"]);
const FILL_COLUMNS=Object.freeze(["open_time","open_price","close_price","broker_history_complete"]);
async function schemaReady(sql){
 const rows=await sql`SELECT table_name,column_name FROM information_schema.columns
  WHERE table_schema='public' AND table_name IN
   ('sentinel_cloud_trader_intents','sentinel_cloud_trader_fills')`;
 const view=await sql`SELECT to_regclass('public.sentinel_cloud_v2_evidence') AS evidence_view`;
 const present=new Set(rows.map(r=>r.table_name+"."+r.column_name));
 const missing=[...INTENT_COLUMNS.filter(x=>!present.has("sentinel_cloud_trader_intents."+x)).map(x=>"intents."+x),
  ...FILL_COLUMNS.filter(x=>!present.has("sentinel_cloud_trader_fills."+x)).map(x=>"fills."+x)];
 if(!view[0]?.evidence_view)missing.push("sentinel_cloud_v2_evidence");
 return {ok:missing.length===0,reason:missing.length?"PREENTRY_MIGRATION_REQUIRED":"PREENTRY_LEDGER_READY",missing};
}
async function freshDemoAuthorization(sql,account,now=Date.now()){
 const rows=await sql`SELECT account_id,expected_last4,expected_server,enabled,expires_at,risk_pct
   FROM sentinel_cloud_trader_authorizations WHERE account_id=${account.id} LIMIT 1`;
 return c.authorizedFusionDemo(rows[0]||null,account,now);
}
module.exports={INTENT_COLUMNS,FILL_COLUMNS,schemaReady,freshDemoAuthorization};
