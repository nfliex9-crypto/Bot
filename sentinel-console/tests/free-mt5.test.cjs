"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const Module=require("node:module");
const orig=Module._load;
let stored="",queries=[];
const sql=async(parts,...args)=>{
 const statement=parts.join("?");
 queries.push({statement,args});
 if(statement.includes("SELECT cipher_value"))return stored?[{cipher_value:stored}]:[];
 if(statement.includes("SELECT config_key"))return stored?[{config_key:"tickerall_api_token"}]:[];
 if(statement.includes("INSERT INTO sentinel_mt5_cloud_config")){stored=args[0];return [];}
 if(statement.includes("DELETE FROM sentinel_mt5_cloud_config")){stored="";return [];}
 return [];
};
Module._load=function(name){
 if(name==="@neondatabase/serverless")return {neon:()=>sql};
 return orig.apply(this,arguments);
};
const handler=require("../api/free-mt5.js");
Module._load=orig;
process.env.DATABASE_URL="postgresql://mock";
process.env.MT5_CLOUD_ENCRYPTION_KEY="ac".repeat(32);
process.env.DASHBOARD_ACCESS_KEY="unit-test-only-secret-abcdefghijklmnop";
function mockRes(){return {statusCode:0,body:null,setHeader(){return this},status(x){this.statusCode=x;return this},json(x){this.body=x;return this}}}
async function call(method,action,body,auth=true){
 const res=mockRes();
 await handler({method,query:{action},headers:auth?{"x-console-key":process.env.DASHBOARD_ACCESS_KEY}:{},body},res);
 return res;
}
test("only authorized keys can access the bridge",async()=>{
 queries=[];
 let r=await call("GET","status",{},false);
 assert.equal(r.statusCode,401);assert.equal(queries.length,0);
});
test("returns genuine not-configured status, no fake account data",async()=>{
 stored="";
 const r=await call("GET","status");
 assert.equal(r.statusCode,200);
 assert.equal(r.body.configured,false);
 assert.deepEqual(r.body.accounts,[]);
});
test("invalid HTTP methods and unsafe actions rejected",async()=>{
 assert.equal((await call("GET","connect",{})).statusCode,405);
 assert.equal((await call("POST","status",{})).statusCode,405);
 assert.equal((await call("POST","place-order",{})).statusCode,404);
});
test("invalid token and broker parameters rejected without provider call",async()=>{
 assert.equal((await call("POST","saveKey",{apiKey:"invalid"})).statusCode,400);
 assert.equal((await call("POST","connect",{account:"notanumber",password:"pwd",server:"Test"})).statusCode,502);
});
test("token validated against provider and encrypted at rest",async()=>{
 const old=global.fetch;
 global.fetch=async(url,init)=>{
  assert.equal(url,"https://api.tickerall.com/v1/accounts");
  assert.equal(init.headers.Authorization,"Bearer cf_api_test_key_1234567890xyz");
  return new Response("[]",{status:200,headers:{"Content-Type":"application/json"}});
 };
 try{
  let r=await call("POST","saveKey",{apiKey:"cf_api_test_key_1234567890xyz"});
  assert.equal(r.statusCode,200);
  assert.equal(r.body.configured,true);
  assert.ok(stored.includes("."));
  assert.ok(!stored.includes("test_key"));
  assert.ok(!JSON.stringify(r.body).includes("test_key"));
 }finally{global.fetch=old}
});
test("account list blocks real accounts and never renders their balances",async()=>{
 const old=global.fetch;
 global.fetch=async()=>new Response(JSON.stringify([
  {id:"acc_DEMO_1",broker:"mt5",server:"Demo",accountNumber:"****1234",isDemo:true,status:"CONNECTED",hot:true},
  {id:"acc_REAL_1",broker:"mt5",server:"Real",accountNumber:"****9999",isDemo:false,status:"CONNECTED",hot:true}
 ]),{status:200});
 try{
  const r=await call("GET","status");
  assert.equal(r.statusCode,200);
  assert.equal(r.body.accounts.length,2);
  assert.equal(r.body.accounts[0].blocked,false);
  assert.equal(r.body.accounts[1].blocked,true);
 }finally{global.fetch=old}
});
test("transient password is forwarded to TickerAll, not database",async()=>{
 queries=[];
 const old=global.fetch;
 global.fetch=async(url,init)=>{
   assert.equal(url,"https://api.tickerall.com/v1/sessions");
   const data=JSON.parse(init.body);
   assert.deepEqual(data,{broker:"mt5",account:"12345678",password:"demo-only-password",server:"Broker-Demo",terminalType:"MOBILE"});
   return new Response(JSON.stringify({accountId:"acc_abcDE12345",isDemo:true,status:"connected"}),{status:200});
 };
 try{
  const r=await call("POST","connect",{account:"12345678",password:"demo-only-password",server:"Broker-Demo"});
  assert.equal(r.statusCode,200);
  assert.equal(r.body.isDemo,true);
  assert.ok(!JSON.stringify(queries).includes("demo-only-password"));
  assert.ok(!JSON.stringify(r.body).includes("demo-only-password"));
 }finally{global.fetch=old}
});
test("real-account responses are blocked fail closed",async()=>{
 const old=global.fetch;
 global.fetch=async()=>new Response(JSON.stringify({accountId:"acc_abcDE12345",isDemo:false,status:"connected"}),{status:200});
 try{assert.equal((await call("POST","connect",{account:"12345678",password:"demo",server:"Broker-Demo"})).statusCode,403)}
 finally{global.fetch=old}
});
test("inspection exposes only verified demo balance",async()=>{
 const old=global.fetch;
 global.fetch=async()=>new Response(JSON.stringify({
  id:"acc_abcDE12345",broker:"mt5",isDemo:true,status:"online",
  account:{accountType:"demo",balance:5000,equity:5011,currency:"USD"},
  positions:[{ticket:10,symbol:"XAUUSD",side:"BUY",volume:.01,profit:11}]
 }),{status:200});
 try{
  const r=await call("POST","inspect",{accountId:"acc_abcDE12345"});
  assert.equal(r.statusCode,200);
  assert.equal(r.body.account.equity,5011);
  assert.equal(r.body.account.positions.length,1);
 }finally{global.fetch=old}
});
