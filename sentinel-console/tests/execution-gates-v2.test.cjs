"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const gates=require("../worker/cloud-trader/execution-gates.js");
const now=Date.UTC(2026,10,23,10);
const account={id:"demo-1964",broker:"mt5",server:"FusionMarkets-Demo",
 isDemo:true,hot:true,readOnly:false,accountNumber:"****1964"};
const permission={account_id:"demo-1964",expected_last4:"1964",
 expected_server:"FusionMarkets-Demo",enabled:true,
 expires_at:new Date(now+3600000).toISOString(),risk_pct:.25};
function sqlFor({columns=true,view=true,approval=permission}={}){
 return async(parts,...args)=>{
  const q=parts.join("?");
  if(q.includes("information_schema.columns"))
   return columns?[
    ...gates.INTENT_COLUMNS.map(column_name=>({table_name:"sentinel_cloud_trader_intents",column_name})),
    ...gates.FILL_COLUMNS.map(column_name=>({table_name:"sentinel_cloud_trader_fills",column_name}))
   ]:[];
  if(q.includes("to_regclass"))return [{evidence_view:view?"sentinel_cloud_v2_evidence":null}];
  if(q.includes("sentinel_cloud_trader_authorizations"))return approval?[approval]:[];
  throw Error("UNEXPECTED_SQL "+q);
 };
}
test("complete migration schema passes without sending orders",async()=>{
 const x=await gates.schemaReady(sqlFor());
 assert.equal(x.ok,true);assert.equal(x.missing.length,0);
});
test("missing ledger columns and view fail closed with exact reasons",async()=>{
 const x=await gates.schemaReady(sqlFor({columns:false,view:false}));
 assert.equal(x.ok,false);assert.ok(x.missing.includes("intents.risk_at_entry"));
 assert.ok(x.missing.includes("fills.open_time"));
 assert.ok(x.missing.includes("sentinel_cloud_v2_evidence"));
});
test("fresh account permission succeeds only for exact, unexpired Fusion Demo",async()=>{
 assert.equal(await gates.freshDemoAuthorization(sqlFor(),account,now),true);
 assert.equal(await gates.freshDemoAuthorization(sqlFor({approval:{...permission,enabled:false}}),account,now),false);
 assert.equal(await gates.freshDemoAuthorization(sqlFor(),account,now+2*3600000),false);
 assert.equal(await gates.freshDemoAuthorization(sqlFor(),{...account,isDemo:false},now),false);
 assert.equal(await gates.freshDemoAuthorization(sqlFor({approval:null}),account,now),false);
});
test("database errors fail closed and never become positive authorization",async()=>{
 await assert.rejects(()=>gates.schemaReady(async()=>{throw Error("DB_DOWN")}),/DB_DOWN/);
 await assert.rejects(()=>gates.freshDemoAuthorization(async()=>{throw Error("DB_DOWN")},account,now),/DB_DOWN/);
});
