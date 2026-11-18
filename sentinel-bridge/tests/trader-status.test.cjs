"use strict";
const test=require("node:test"),assert=require("node:assert/strict");
const {normalize}=require("../trader-contract.js");
const now=Date.UTC(2026,10,18,16);
const example=()=>({source:"SENTINEL_INDEPENDENT_TRADER",account_last4:"4444",mode:"research",
 execution_armed:false,timestamp:new Date(now).toISOString(),symbols:[{symbol:"XAUUSD",
 status:"RESEARCH_SIGNAL",strategy:"trend_pullback",side:"LONG",order_submissions:0}]});
test("demo trader statuses are read-only unverified device telemetry",()=>{
 const r=normalize(example(),now);
 assert.equal(r.execution_proof,"UNVERIFIED_DEVICE_TELEMETRY_NOT_BROKER_FILL_CONFIRMATION");
 assert.equal(r.symbols[0].order_submissions,0);
});
test("reject forged, stale, oversized or unrecognized status payloads",()=>{
 for(const input of [
  {...example(),mode:"real"}, {...example(),source:"GROK"},
  {...example(),timestamp:new Date(now-100000).toISOString()},
  {...example(),account_last4:"22224444"},
  {...example(),symbols:[{symbol:"XAUUSD",status:"PLACE_ORDER"}]},
  {...example(),symbols:Array.from({length:9},()=>example().symbols[0])},
 ])assert.equal(normalize(input,now),null);
});
