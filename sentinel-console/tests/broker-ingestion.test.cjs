"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const ingest=require("../brain/broker-ingestion.js");
function sample(now,spread=.04){
 const last=Math.floor(now.getTime()/900000)*900000;
 const start=last-1099*900000;
 return Array.from({length:1100},(_,i)=>({
  timestamp:(start+i*900000)/1000,open:100+i*.001,
  high:100.12+i*.001,low:99.9+i*.001,
  close:100.04+i*.001,spread,tickVolume:80+i%7
 }));
}
test("MT5 broker-symbol discovery keeps native names, priority and weekend restrictions",()=>{
 const raw={symbols:["XAUUSDm","BTCUSD","EURUSD","USTECH100M","NOT_ALLOWED"]};
 const week=new Date("2026-11-18T11:00:00Z");
 assert.deepEqual(ingest.selectMarkets(raw,week),
  ["XAUUSDm","BTCUSD","EURUSD","USTECH100M"]);
 assert.deepEqual(ingest.selectMarkets(raw,new Date("2026-11-21T11:00:00Z")),["BTCUSD"]);
});
test("one job per cycle: never retry the same timed-out symbol before untried markets",()=>{
 const now=new Date("2026-11-18T11:15:00Z"),symbols=["XAUUSD","EURUSD"];
 const attempted=[
  {symbol:"XAUUSD",timeframe:"M15",status:"ERROR",attempted_at:"2026-11-18T11:00:00Z"}
 ];
 const job=ingest.selectJob(symbols,attempted,now);
 assert.deepEqual({symbol:job.symbol,timeframe:job.timeframe},
  {symbol:"XAUUSD",timeframe:"H1"});
 const fullyAttempted=["XAUUSD","EURUSD"].flatMap(s=>["M15","H1"].map(tf=>({
  symbol:s,timeframe:tf,status:"STORED_RESEARCH_BLOCKED",
  attempted_at:"2026-11-18T11:00:00Z"
 })));
 assert.equal(ingest.selectJob(symbols,fullyAttempted,now),null);
});
test("heavy gold and NAS100 histories use smaller windows, timeouts back off to a compact retry",()=>{
 const jobs=ingest.selectableJobs(["XAUUSD","USTECH100M","EURUSD"]);
 const gold=jobs.find(x=>x.symbol==="XAUUSD"&&x.timeframe==="M15");
 const nas=jobs.find(x=>x.symbol==="USTECH100M"&&x.timeframe==="H1");
 const fx=jobs.find(x=>x.symbol==="EURUSD"&&x.timeframe==="M15");
 assert.equal(gold.hours,336);
 assert.equal(nas.hours,720);
 assert.equal(fx.hours,1440);
 const prior=[
  {symbol:"XAUUSD",timeframe:"M15",status:"ERROR",attempted_at:"2026-11-18T11:00:00Z"},
  {symbol:"XAUUSD",timeframe:"H1",status:"STORED_RESEARCH_BLOCKED",attempted_at:"2026-11-18T11:30:00Z"}
 ];
 const retry=ingest.selectJob(["XAUUSD"],prior,new Date("2026-11-18T11:45:00Z"));
 assert.equal(retry.timeframe,"M15");
 assert.equal(retry.hours,24);
});
test("slow broker windows expand only after successful compact snapshots",()=>{
 const now=new Date("2026-11-18T15:00:00Z");
 for(const [stored_rows,expected] of [[0,24],[30,72],[220,168],[700,336]]){
  const job=ingest.selectJob(["XAUUSD"],[{symbol:"XAUUSD",timeframe:"M15",
    attempted_at:"2026-11-18T12:00:00Z",status:"STORED_RESEARCH_BLOCKED",stored_rows},
   {symbol:"XAUUSD",timeframe:"H1",attempted_at:"2026-11-18T14:50:00Z",status:"ERROR"}],now);
  assert.equal(job.hours,expected);
 }
 assert.equal(ingest.adaptiveHours({symbol:"USTECH100M",timeframe:"H1",hours:720},
  {status:"ERROR",stored:0}),24);
});
test("provider Unix seconds become closed UTC bars, and open candle is excluded",()=>{
 const now=new Date("2026-11-18T12:07:00Z");
 const result=ingest.normalizeBatch({coverage:"complete",truncated:false,candles:sample(now)},
  {timeframe:"M15",now});
 assert.equal(result.accepted,1099);
 assert.equal(result.quality.open_bar_excluded,1);
 assert.equal(result.quality.missing_spread_ratio,0);
 assert.equal(result.safeForResearch,true);
 assert.equal(new Date(result.bars.at(-1).timestamp).toISOString(),"2026-11-18T11:45:00.000Z");
});
test("genuine historical candles with absent spread stay stored but cannot earn a paper reward",()=>{
 const now=new Date("2026-11-18T12:07:00Z");
 const result=ingest.normalizeBatch({coverage:"complete",truncated:false,candles:sample(now,null)},
  {timeframe:"M15",now});
 assert.equal(result.accepted,1099);
 assert.equal(result.quality.missing_spread_ratio,1);
 assert.equal(result.safeForResearch,false);
 assert.ok(result.bars.every(x=>x.spread===null));
});
test("truncated or partial provider data never become clean backtest evidence",()=>{
 const now=new Date("2026-11-18T12:07:00Z");
 for(const item of [{coverage:"partial",truncated:false},{coverage:"complete",truncated:true}]){
  const x=ingest.normalizeBatch({...item,candles:sample(now)},{timeframe:"M15",now});
  assert.equal(x.safeForResearch,false);
 }
});
test("rejects timestamps in the future while preserving valid historical rows",()=>{
 const now=new Date("2026-11-18T12:07:00Z");
 const rows=sample(now);
 rows[0].timestamp=Date.UTC(2099,0,1)/1000;
 const result=ingest.normalizeBatch({coverage:"complete",truncated:false,candles:rows},
  {timeframe:"M15",now});
 assert.equal(result.safeForResearch,false);
 assert.equal(result.quality.open_bar_excluded,1);
 assert.equal(result.quality.bad_timestamps,1);
 assert.equal(result.quality.missing_spread_ratio,0);
});

test("scheduled demo worker imports genuine broker candles and reports missing-spread quality without orders",async()=>{
 const crypto=require("node:crypto"),Module=require("node:module");
 const oldLoad=Module._load;
 Module._load=function(request){
  if(request==="@neondatabase/serverless")return {neon:()=>{throw Error("REAL_DATABASE_FORBIDDEN_IN_TEST")}};
  return oldLoad.apply(this,arguments);
 };
 const worker=require("../worker/runner.js");
 Module._load=oldLoad;
 const key="cd".repeat(32),iv=Buffer.alloc(12,7),cipher=crypto.createCipheriv("aes-256-gcm",Buffer.from(key,"hex"),iv);
 const token="cf_api_unit_fake_abcdefghijklmnop";
 const bytes=Buffer.concat([cipher.update(token,"utf8"),cipher.final()]);
 const encrypted=[iv,cipher.getAuthTag(),bytes].map(x=>x.toString("base64")).join(".");
 const oldKey=process.env.MT5_CLOUD_ENCRYPTION_KEY;
 process.env.MT5_CLOUD_ENCRYPTION_KEY=key;
 const queries=[];
 const now=new Date("2026-11-18T12:07:00Z");
 async function sql(parts,...values){
  const query=parts.join("?");queries.push({query,values});
  if(query.includes("SELECT cipher_value"))return [{cipher_value:encrypted}];
  if(query.includes("SELECT symbol,timeframe,attempted_at"))return [];
  if(query.includes("SELECT spec FROM sentinel_autonomy_candidates"))return [];
  if(query.includes("SELECT MAX(created_at)"))return [{last_run:now}];
  return [];
 }
 const visited=[];
 async function fetcher(url,headers){
  visited.push(url);
  if(url.endsWith("/v1/accounts"))return [{id:"acc_demo_testing_123",isDemo:true,hot:true,status:"CONNECTED",broker:"mt5"}];
  if(url.endsWith("/symbols"))return {symbols:["XAUUSD","EURUSD","BTCUSD"]};
  if(url.includes("/candles?"))return {coverage:"complete",truncated:false,candles:sample(now,null)};
  throw Error("UNEXPECTED_EXTERNAL_SOURCE");
 }
 try{
  const out=await worker.researchCycle(sql,{now,fetcher});
  assert.equal(out.status,"COMPLETED");
  assert.equal(out.totals.markets,1);
  assert.equal(out.totals.candidates,0);
  assert.equal(out.orders_executed,0);
  const result=queries.find(x=>x.query.includes("INSERT INTO sentinel_autonomy_import_attempts"));
  assert.ok(result);
  assert.ok(queries.some(x=>x.query.includes("INSERT INTO sentinel_brain_candles")));
  assert.equal(visited.filter(x=>x.includes("/candles?")).length,1);
  assert.ok(!visited.some(x=>x.includes("/orders")));
  assert.ok(!JSON.stringify(out).includes(token));
 }finally{
  if(oldKey===undefined)delete process.env.MT5_CLOUD_ENCRYPTION_KEY;
  else process.env.MT5_CLOUD_ENCRYPTION_KEY=oldKey;
 }
});
