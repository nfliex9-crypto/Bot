"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const Module=require("node:module");
const originalLoad=Module._load;
let dbQueries=[],cipherValue="";
const sql=async(parts,...values)=>{
  const q=parts.join("?");
  dbQueries.push({q,values});
  if(q.includes("SELECT cipher_value FROM sentinel_mt5_cloud_config"))return cipherValue?[{cipher_value:cipherValue}]:[];
  if(q.includes("SELECT config_key FROM sentinel_mt5_cloud_config"))return cipherValue?[{config_key:"metaapi_token"}]:[];
  if(q.includes("SELECT id,account_label"))return [];
  if(q.includes("INSERT INTO sentinel_mt5_cloud_config")){
    cipherValue=values[0];return [];
  }
  return [];
};
Module._load=function(request,parent,isMain){
 if(request==="@neondatabase/serverless")return {neon:()=>sql};
 return originalLoad.apply(this,arguments);
};
const handler=require("../api/cloud.js");
Module._load=originalLoad;
process.env.DATABASE_URL="postgres://fake-for-unit-testing";
process.env.DASHBOARD_ACCESS_KEY="unittest-access-key-abcdefghijklmnopqrstuvwxyz";
process.env.MT5_CLOUD_ENCRYPTION_KEY="ab".repeat(32);
function res(){
 return {code:0,body:null,headers:{},setHeader(k,v){this.headers[k]=v;return this},
  status(v){this.code=v;return this},json(v){this.body=v;return this}};
}
async function call(method,action,body,authorized=true){
 const r=res();
 await handler({method,query:{action},body,headers:authorized?{"x-console-key":process.env.DASHBOARD_ACCESS_KEY}:{}},r);
 return r;
}
test("rejects unauthenticated status before database calls",async()=>{
 dbQueries=[];
 const r=await call("GET","status",null,false);
 assert.equal(r.code,401);
 assert.equal(dbQueries.length,0);
});
test("returns empty state without linking any account",async()=>{
 const r=await call("GET","status");
 assert.equal(r.code,200);
 assert.equal(r.body.token_configured,false);
 assert.deepEqual(r.body.accounts,[]);
});
test("only allowlisted method per endpoint is accepted",async()=>{
 assert.equal((await call("POST","status",{})).code,405);
 assert.equal((await call("GET","token",{})).code,405);
 assert.equal((await call("GET","nonexistent")).code,405); // no route accepted
});
test("invalid MetaApi token never gets stored",async()=>{
 dbQueries=[];
 const r=await call("POST","token",{token:"short"});
 assert.equal(r.code,400);
 assert.equal(dbQueries.length,0);
});
test("MetaApi token validation and AES-GCM encryption never expose secret",async()=>{
 const originalFetch=global.fetch;
 global.fetch=async(url,options)=>{
  assert.ok(String(url).startsWith("https://mt-provisioning-api-v1.agiliumtrade.agiliumtrade.ai/"));
  assert.equal(options.headers["auth-token"],"unit-test-only-api-token-1234567890");
  return new Response("[]",{status:200,headers:{"Content-Type":"application/json"}});
 };
 try{
  const r=await call("POST","token",{token:"unit-test-only-api-token-1234567890"});
  assert.equal(r.code,200);
  assert.equal(r.body.token_configured,true);
  assert.equal(r.body.available_mt5_accounts,0);
  assert.ok(cipherValue.includes("."));
  assert.ok(!cipherValue.includes("unit-test-only-api-token"));
  assert.ok(!JSON.stringify(r.body).includes("unit-test-only-api-token"));
 } finally {global.fetch=originalFetch}
});
test("only explicitly broker-confirmed demo can be marked connected",()=>{
 const fs=require("node:fs");
 const code=fs.readFileSync(require("node:path").join(__dirname,"../api/cloud.js"),"utf8");
 assert.match(code,/info\?\.type==="ACCOUNT_TRADE_MODE_DEMO"/);
 assert.match(code,/tradeMode="REJECTED_NON_DEMO"/);
 assert.match(code,/connection_status==="CONNECTED"&&r\.verified_trade_mode==="DEMO"/);
 assert.ok(!code.includes('method:"POST",headers:{"auth-token"')); // no client trade endpoint
});
