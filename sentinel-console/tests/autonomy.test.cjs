"use strict";
const test=require("node:test"),assert=require("node:assert/strict");
const factory=require("../brain/strategy-factory.js");
const worker=require("../worker/runner.js");
const radar=require("../brain/research-radar.js");
const crypto=require("node:crypto");
function fixture(n=1200,{missingSpread=false}={}){
 const bars=[];let close=1900;
 for(let i=0;i<n;i++){const open=close;close=Math.max(1,open+Math.sin(i/7)*2+Math.sin(i/59)*.7+.04);
  bars.push({timestamp:Date.UTC(2026,5,1)+i*900000,open,close,
   high:Math.max(open,close)+1,low:Math.min(open,close)-1,
   spread:missingSpread?null:.18,tickVolume:100+i%13})}
 return bars;
}
test("generates bounded rule variants with stable content IDs",()=>{
 const list=factory.seeds();
 assert.equal(list.length,16);
 assert.equal(new Set(list.map(x=>x.id)).size,16);
 assert.deepEqual(factory.seeds(),list);
 const offspring=factory.createChildren(list,"2026-11-18");
 assert.ok(offspring.length>0&&offspring.length<=8);
 assert.ok(offspring.every(s=>!list.some(p=>p.id===s.id)));
});
test("historical research does not accept missing broker spread, or incomplete provider coverage",()=>{
 for(const [bars,source] of [
  [fixture(1400,{missingSpread:true}),{coverage:"complete",truncated:false}],
  [fixture(1400),{coverage:"partial",truncated:true}]
 ]){
  const r=factory.scoreFamily(bars,source);
  assert.equal(r.status,"INSUFFICIENT_REAL_HISTORY");
  assert.equal(r.candidates.length,0);
  assert.equal(r.orders_enabled,false);
 }
});
test("factory evaluates disjoint OOS windows without enabling any order",()=>{
 const r=factory.scoreFamily(fixture(3400),{coverage:"complete",truncated:false,cycleId:"unit"});
 assert.equal(r.candidates.length,16);
 assert.equal(r.orders_enabled,false);
 assert.equal(r.risk_multiplier,1);
 for(const c of r.candidates){
  assert.ok(["BOOST_PAPER_RESEARCH_2X","RETIRE_PAPER_RESEARCH","OBSERVE_MORE"].includes(c.status));
  assert.ok(c.holdout.trades>=0);
  assert.ok(c.robustness.tests_screened===16);
  assert.equal(c.orders_enabled,false);
  if(c.priority_multiplier===2){
   assert.ok(c.robustness.eligible_for_paper_research);
   assert.ok(c.holdout.expectancy_r>0);
  }
 }
});
test("weekend broker symbol picker excludes closed FX/gold but retains listed crypto only",()=>{
 const symbols={symbols:["GOLD","BTCUSD","EURUSD","NAS100"]};
 const fri=worker.selectMarkets(symbols,new Date("2026-11-20T15:00:00Z"));
 const sat=worker.selectMarkets(symbols,new Date("2026-11-21T15:00:00Z"));
 assert.deepEqual(fri,["GOLD","BTCUSD","EURUSD","NAS100"]);
 assert.deepEqual(sat,["BTCUSD"]);
 assert.deepEqual(worker.selectMarkets({symbols:["XAUUSD","EURUSD"]},new Date("2026-11-21T15:00:00Z")),[]);
});
test("worker refuses unauthorized external endpoints and never uses order endpoints",async()=>{
 await assert.rejects(()=>worker.fetchJSON("https://attacker.example/evil"),/SOURCE_NOT_ALLOWLISTED/);
 await assert.rejects(()=>worker.fetchJSON("https://api.tickerall.com/v1/accounts/abcd/orders"),/BROKER_HTTP_|/);
 const src=require("node:fs").readFileSync(require("node:path").join(__dirname,"../worker/runner.js"),"utf8");
 assert.doesNotMatch(src,/(?:\+["']\/orders|\/positions\/|method:\s*["']POST["'])/);
});
test("empty worker state is honest and produces no phantom trades",async()=>{
 const saved=process.env.MT5_CLOUD_ENCRYPTION_KEY;
 delete process.env.MT5_CLOUD_ENCRYPTION_KEY;
 const calls=[];
 async function sql(parts,...args){
  calls.push(parts.join("?"));
  if(parts.join("").includes("SELECT cipher_value"))return [];
  if(parts.join("").includes("SELECT account_id,symbol,timeframe"))return [];
  return [];
 }
 try{
  const r=await worker.researchCycle(sql,{now:new Date("2026-11-18T01:30:00Z"),
   fetcher:()=>{throw Error("NETWORK_SHOULD_NOT_BE_CALLED")}});
  assert.equal(r.status,"WAITING_FOR_REAL_DATA");
  assert.equal(r.totals.candidates,0);
  assert.equal(r.orders_executed,0);
  assert.ok(calls.some(c=>c.includes("sentinel_autonomy_cycles")));
 }finally{
  if(saved!==undefined)process.env.MT5_CLOUD_ENCRYPTION_KEY=saved;
 }
});
test("Crossref radar stores bibliographic metadata only; does not invent research conclusions",async()=>{
 const r=await radar.researchRadar({topics:[{name:"test",query:"foreign exchange volatility"}],fetchJSON:async()=>({
  message:{items:[{DOI:"10.1234/market.2025",title:["Intraday gold futures volatility"],
   published:{"date-parts":[[2025,3,1]]}},{DOI:"invalid",title:["X"]}]}
 })});
 assert.equal(r.items.length,1);
 assert.match(r.items[0].source_url,/doi.org/);
 assert.equal(r.items[0].source_kind,"BIBLIOGRAPHIC_METADATA_NOT_VERIFIED_STRATEGY");
 assert.equal(r.not_used_for_orders,true);
});
