"use strict";
const test=require("node:test"),assert=require("node:assert/strict");
const {tradeMemory}=require("../brain/trade-memory.js");
const start=Date.parse("2026-09-01T09:00:00Z");
function rows(count,profit=-10,symbol="XAUUSD"){
 return Array.from({length:count},(_,i)=>({
  symbol,side:i%2?"SELL":"BUY",complete:true,brokerProfit:profit,
  openTime:new Date(start+i*86400000).toISOString(),
  closeTime:new Date(start+i*86400000+3600000).toISOString()
 }));
}
test("every completed broker trade contributes to account memory without invented strategy labels",()=>{
 const r=tradeMemory([...rows(30,15),...rows(10,-5,"EURUSD")]);
 assert.equal(r.quality.completed,40);
 assert.equal(r.overall.trades,40);
 assert.equal(r.by_symbol.length,2);
 assert.equal(r.by_symbol.find(x=>x.name==="XAUUSD").trades,30);
 assert.equal(r.orders_enabled,false);
 assert.equal(r.quality.attribution_required_for_strategy_selection,true);
});
test("persistent negative market and recent performance are flagged for paper research only",()=>{
 const r=tradeMemory(rows(35,-20));
 const x=r.by_symbol[0];
 assert.equal(x.status,"AVOID_PAPER_EXPERIMENTS");
 assert.equal(x.broker_reported_profit,-700);
 assert.equal(r.orders_enabled,false);
});
test("unverified, incomplete and invalid broker records never enter performance calculations",()=>{
 const data=rows(3,20);
 data.push({symbol:"XAUUSD",complete:false,brokerProfit:2000,closeTime:"2026-11-18T10:00:00Z"});
 data.push({symbol:"XAUUSD",complete:true,brokerProfit:null,closeTime:"2026-11-18T10:00:00Z"});
 const r=tradeMemory(data);
 assert.equal(r.overall.trades,3);
 assert.equal(r.quality.skipped,2);
});
test("missing entry timestamp falls back to actual close session, not 1970",()=>{
 const r=tradeMemory([{
  symbol:"EURUSD",side:"BUY",complete:true,brokerProfit:2,
  openTime:null,closeTime:"2026-11-18T15:00:00Z"
 }]);
 assert.equal(r.quality.missing_entry_time,1);
 assert.equal(r.by_session[0].name,"new_york");
});
test("positive performance can only suggest more paper research, never an order",()=>{
 const vals=rows(40,25).map((x,i)=>({...x,brokerProfit:i%5===0?-20:25}));
 const r=tradeMemory(vals);
 assert.equal(r.by_symbol[0].status,"REVIEW_FOR_MORE_PAPER_TESTS");
 assert.equal(r.orders_enabled,false);
});
