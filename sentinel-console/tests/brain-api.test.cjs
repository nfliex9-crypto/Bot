"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const crypto=require("node:crypto"),Module=require("node:module");
let dbCalls=[],keyStored="";
const key=Buffer.from("df".repeat(32),"hex");
function encrypt(v){
 const iv=crypto.randomBytes(12),c=crypto.createCipheriv("aes-256-gcm",key,iv);
 return [iv,c.getAuthTag?null:null].length===0?"":(()=>{
  const content=Buffer.concat([c.update(v,"utf8"),c.final()]);
  return [iv.toString("base64"),c.getAuthTag().toString("base64"),content.toString("base64")].join(".")
 })();
}
keyStored=encrypt("cf_api_test_only_Brain_23456890xyz");
const sql=async(strings,...values)=>{
 const q=strings.join("?");
 dbCalls.push({q,values});
 if(q.includes("SELECT cipher_value FROM sentinel_mt5_cloud_config"))return [{cipher_value:keyStored}];
 if(q.includes("SELECT account_id,COUNT(*)"))return [];
 if(q.includes("FROM sentinel_brain_candles")&&q.includes("COUNT(*)"))return [{count:0}];
 if(q.includes("FROM sentinel_brain_runs")&&q.includes("ORDER BY created_at"))return [];
 if(q.includes("FROM sentinel_brain_imports")&&q.includes("ORDER BY imported_at"))return [];
 if(q.includes("SELECT ticket,close_time,broker_profit,complete,strategy_id"))return [];
 if(q.includes("FROM sentinel_brain_imports")&&q.includes("WHERE account_id"))return [];
 if(q.includes("FROM sentinel_brain_candles")&&q.includes("ORDER BY bar_time"))return [];
 if(q.includes("SELECT COUNT(*)")&&q.includes("sentinel_brain_trades"))return [{count:0}];
 return [];
};
const oldLoad=Module._load;
Module._load=function(name){
 if(name==="@neondatabase/serverless")return {neon:()=>sql};
 return oldLoad.apply(this,arguments);
};
const handler=require("../api/brain.js");
Module._load=oldLoad;
process.env.DATABASE_URL="postgres://unit-test";
process.env.MT5_CLOUD_ENCRYPTION_KEY=key.toString("hex");
process.env.SENTINEL_VERCEL_SSO="enabled";
async function run(action,body,method){
 const resp={code:0,body:null,setHeader(){return this},status(v){this.code=v;return this},json(v){this.body=v;return this}};
 await handler({method:method||(body===undefined?"GET":"POST"),
 query:{action},body,headers:{host:"sentinel-mt5-console.vercel.app",origin:"https://sentinel-mt5-console.vercel.app"}},resp);
 return resp;
}
test("rejects unknown action or method without connecting to broker",async()=>{
 dbCalls=[];
 assert.equal((await run("placeOrder",{})).code,404);
 assert.equal((await run("syncTrades",{},"GET")).code,405);
 assert.equal(dbCalls.length,0);
});
test("SSO missing rejects all research access",async()=>{
 const prev=process.env.SENTINEL_VERCEL_SSO;
 delete process.env.SENTINEL_VERCEL_SSO;
 try{assert.equal((await run("status")).code,403)}
 finally{process.env.SENTINEL_VERCEL_SSO=prev}
});
test("initial empty research status never fabricates historical results",async()=>{
 const r=await run("status");
 assert.equal(r.code,200);
 assert.equal(r.body.data.real_trades,0);
 assert.equal(r.body.data.candles,0);
 assert.deepEqual(r.body.data.runs,[]);
 assert.equal(r.body.data.execution_enabled,false);
});
test("only TickerAll confirmed Demo can be imported",async()=>{
 const old=global.fetch;
 dbCalls=[];
 global.fetch=async()=>new Response(JSON.stringify([{id:"acc_test123",broker:"mt5",isDemo:false,hot:true}]),{status:200});
 try{
  const r=await run("syncTrades",{accountId:"acc_test123"});
  assert.equal(r.code,422);
  assert.equal(r.body.error,"DEMO_ACCOUNT_REQUIRED");
  assert.equal(dbCalls.filter(x=>x.q.includes("INSERT INTO sentinel_brain_trades")).length,0);
 }finally{global.fetch=old}
});
test("syncs true closed trade but does not invent strategy identity",async()=>{
 const old=global.fetch;
 dbCalls=[];
 global.fetch=async(url)=>{
  if(String(url).endsWith("/v1/accounts"))return new Response(JSON.stringify([{id:"acc_test123",broker:"mt5",isDemo:true,hot:true}]),{status:200});
  assert.ok(String(url).includes("/history?limit=5000"));
  return new Response(JSON.stringify({trades:[{
   ticket:"991",symbol:"GOLD",side:"BUY",openTime:"2026-11-18T09:00:00Z",
   closeTime:"2026-11-18T09:30:00Z",profit:13,volume:.01,complete:true,
   commission:0,swap:0
  }]}),{status:200});
 };
 try{
  const r=await run("syncTrades",{accountId:"acc_test123"});
  assert.equal(r.code,200);
  assert.equal(r.body.data.normalized,1);
  assert.equal(r.body.data.fee_data_complete,false);
  const insertion=dbCalls.find(x=>x.q.includes("INSERT INTO sentinel_brain_trades"));
  assert.ok(insertion);
  assert.ok(!insertion.q.includes("strategy_id"));
  assert.ok(insertion.values.some(v=>String(v).includes('"ticket":"991"')));
 }finally{global.fetch=old}
});
test("downloads real historical candles, preserves provider completeness",async()=>{
 const old=global.fetch;
 dbCalls=[];
 global.fetch=async(url)=>{
  if(String(url).endsWith("/v1/accounts"))return new Response(JSON.stringify([{id:"acc_test123",broker:"mt5",isDemo:true,hot:true}]),{status:200});
  assert.ok(String(url).includes("/candles?"));
  const candles=Array.from({length:340},(_,i)=>({timestamp:1760000000+i*900,
   open:100+i*.01,high:101+i*.01,low:99+i*.01,close:100.1+i*.01,spread:.04}));
  return new Response(JSON.stringify({candles,coverage:"partial",truncated:true,stopReason:"deadline"}),{status:200});
 };
 try{
  const r=await run("syncCandles",{accountId:"acc_test123",symbol:"EURUSD",timeframe:"M15",hours:720});
  assert.equal(r.code,200);
  assert.equal(r.body.data.received,340);
  assert.equal(r.body.data.truncated,true);
  assert.equal(r.body.data.coverage,"partial");
  assert.ok(dbCalls.some(x=>x.q.includes("INSERT INTO sentinel_brain_imports")));
 }finally{global.fetch=old}
});
test("refuses analysis with zero imported broker history",async()=>{
 const r=await run("evaluate",{accountId:"acc_test123",symbol:"EURUSD",timeframe:"M15"});
 assert.equal(r.code,422);
 assert.equal(r.body.error,"IMPORT_HISTORY_FIRST");
});

test("old open positions cannot be retroactively assigned to a winning strategy",async()=>{
 const previous=global.fetch;
 dbCalls=[];
 global.fetch=async(url)=>{
  if(String(url).endsWith("/v1/accounts"))return new Response(JSON.stringify([
    {id:"acc_test123",broker:"mt5",isDemo:true,hot:true}
  ]),{status:200});
  return new Response(JSON.stringify({
    id:"acc_test123",isDemo:true,status:"online",account:{accountType:"demo"},
    positions:[{ticket:991,symbol:"EURUSD",openTime:new Date(Date.now()-3600000).toISOString()}]
  }),{status:200});
 };
 try{
  const r=await run("tagPosition",{accountId:"acc_test123",ticket:"991",
    strategyId:"ema_pullback",riskAmount:10});
  assert.equal(r.code,422);
  assert.equal(r.body.error,"TAG_WINDOW_EXPIRED");
  assert.ok(!dbCalls.some(q=>q.q.includes("INSERT INTO sentinel_brain_order_tags")));
 }finally{global.fetch=previous}
});
test("new actual DEMO open position can be attributed immutably without sending orders",async()=>{
 const previous=global.fetch;dbCalls=[];
 global.fetch=async(url)=>{
  if(String(url).endsWith("/v1/accounts"))return new Response(JSON.stringify([
    {id:"acc_test123",broker:"mt5",isDemo:true,hot:true}
  ]),{status:200});
  return new Response(JSON.stringify({
    id:"acc_test123",isDemo:true,status:"online",account:{accountType:"demo"},
    positions:[{ticket:991,symbol:"EURUSD",openTime:new Date(Date.now()-10000).toISOString()}]
  }),{status:200});
 };
 try{
  const r=await run("tagPosition",{accountId:"acc_test123",ticket:"991",
    strategyId:"ema_pullback",riskAmount:10});
  assert.equal(r.code,200);
  assert.equal(r.body.data.order_submitted,false);
  const insert=dbCalls.find(x=>x.q.includes("INSERT INTO sentinel_brain_order_tags"));
  assert.ok(insert);
  assert.ok(insert.q.includes("ON CONFLICT(account_id,ticket) DO NOTHING"));
 }finally{global.fetch=previous}
});
