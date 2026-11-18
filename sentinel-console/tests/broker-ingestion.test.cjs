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
 assert.equal(result.quality.open_bar_excluded,2);
 assert.equal(result.quality.missing_spread_ratio,0);
});
