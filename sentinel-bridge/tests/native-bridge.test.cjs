"use strict";
const test=require("node:test"),assert=require("node:assert/strict");
const Module=require("node:module"),oldLoad=Module._load;
const queries=[];
let active=[];
const sql=async(parts,...params)=>{
 const text=parts.join("?");
 queries.push({text,params});
 if(text.includes("SELECT account_last4"))return active;
 return [];
};
Module._load=function(name){
 if(name==="@neondatabase/serverless")return {neon:()=>sql};
 return oldLoad.apply(this,arguments);
};
const endpoint=require("../api/mt5.js");
Module._load=oldLoad;
function res(){
 return {code:0,payload:null,setHeader(){return this;},
  status(n){this.code=n;return this},json(x){this.payload=x;return this}};
}
const agentId="12345678-1234-1234-1234-1234567890ab",token="ab".repeat(32);
function request(){
 const stamp=Math.floor(Date.now()/900000)*900-1800;
 return {
  method:"POST",query:{action:"candles"},
  headers:{"x-mt5-agent-id":agentId,"x-mt5-agent-token":token},
  body:{source:"LOCAL_MT5_DEMO_TERMINAL",trade_mode:"demo",
   symbol:"XAUUSD",timeframe:"M15",account_last4:"3445",
   candles:[{timestamp:stamp,open:4000,high:4010,low:3998,close:4005,spread:.12,tickVolume:700}]}
 };
}
test("paired fresh DEMO agent is mandatory before any native history write",async()=>{
 const orig=process.env.DATABASE_URL;process.env.DATABASE_URL="test-neon-invalid";
 try{
  queries.length=0;active=[];
  const response=res();await endpoint(request(),response);
  assert.equal(response.code,403);assert.equal(response.payload.error,"FRESH_DEMO_HEARTBEAT_REQUIRED");
  assert.ok(!queries.some(q=>q.text.includes("INSERT INTO sentinel_brain_candles")));
 }finally{if(orig===undefined)delete process.env.DATABASE_URL;else process.env.DATABASE_URL=orig}
});
test("valid DEMO payload is stored only as unverified isolated research",async()=>{
 const orig=process.env.DATABASE_URL;process.env.DATABASE_URL="test-neon-invalid";
 try{
  queries.length=0;active=[{account_last4:"3445"}];
  const response=res();await endpoint(request(),response);
  assert.equal(response.code,202);
  assert.equal(response.payload.orders_executed,0);
  assert.equal(response.payload.unverified,true);
  assert.ok(queries.some(q=>q.text.includes("INSERT INTO sentinel_brain_candles")&&q.params.some(p=>p==="native-demo-"+agentId)));
  assert.ok(queries.some(q=>q.text.includes("INSERT INTO sentinel_brain_imports")&&q.text.includes("local_unverified")));
  assert.ok(!queries.some(q=>/orders|positions|reward_points/.test(q.text)));
 }finally{if(orig===undefined)delete process.env.DATABASE_URL;else process.env.DATABASE_URL=orig}
});
test("paired agent cannot upload bars from another demo account or real account",async()=>{
 const orig=process.env.DATABASE_URL;process.env.DATABASE_URL="test-neon-invalid";
 try{
  queries.length=0;active=[{account_last4:"3445"}];
  const r=request();r.body.account_last4="9999";
  const response=res();await endpoint(r,response);
  assert.equal(response.code,403);assert.equal(response.payload.error,"ACCOUNT_MISMATCH");
  assert.ok(!queries.some(q=>q.text.includes("INSERT INTO sentinel_brain_candles")));
 }finally{if(orig===undefined)delete process.env.DATABASE_URL;else process.env.DATABASE_URL=orig}
});
