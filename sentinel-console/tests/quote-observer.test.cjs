"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const {readQuote,recordQuote}=require("../brain/quote-observer.js");
test("authentic MT5 quote is timestamped at collection and spread computed from bid/ask",()=>{
 const now=new Date("2026-11-18T11:15:00Z");
 const x=readQuote({symbol:"EURUSD",bid:1.07241,ask:1.07249},
  {accountId:"acc_test",symbol:"EURUSD",now});
 assert.equal(x.observed,true);
 assert.equal(x.status,"OBSERVED");
 assert.equal(x.at,now.toISOString());
 assert.ok(x.spread_bps>0);
 assert.ok(Math.abs(x.spread-.00008)<1e-10);
});
test("closed market or inverted quotes are never stored as a zero spread",async()=>{
 let calls=0;
 const sql=async()=>{calls++;return []};
 for(const raw of [
  {symbol:"GOLD",bid:null,ask:null},
  {symbol:"GOLD",bid:0,ask:0},
  {symbol:"GOLD",bid:2100,ask:2099.9},
  {symbol:"GOLD",bid:"2100",ask:"2100.2"}
 ]){
  const r=await recordQuote(sql,{accountId:"acc_test",symbol:"GOLD",raw});
  assert.equal(r.observed,false);
 }
 assert.equal(calls,0);
});
test("quote SQL inserts only measured MT5 prices and lets Postgres compute exact decimal spread",async()=>{
 const records=[];
 const sql=async(parts,...args)=>{records.push({q:parts.join("?"),args});return []};
 const x=await recordQuote(sql,{accountId:"acc_demo",symbol:"EURUSD",
  raw:{bid:1.07241,ask:1.07249},now:new Date("2026-11-18T11:15:00Z")});
 assert.equal(x.observed,true);
 assert.equal(records.length,1);
 assert.match(records[0].q,/sentinel_autonomy_spread_observations/);
 assert.match(records[0].q,/::numeric-\?::numeric/);
 assert.doesNotMatch(records[0].q,/orders|close.position/i);
 assert.ok(!records[0].q.includes("password"));
});
