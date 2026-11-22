"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const replay=require("../brain/broker-gross-replay.js");
const ms15=900000,ms60=3600000,base=Date.UTC(2026,9,1),asOf=Date.UTC(2026,10,22);
function bars(n,tf){
 return Array.from({length:n},(_,i)=>{const open=1.1+i*.00003,close=open+.00002;
  return {time:base+i*tf,open,high:close+.00008,low:open-.00008,close}});
}
const fixture=()=>({symbol:"EURUSD",m15:bars(220,ms15),h1:bars(140,ms60),asOf});
test("broker gross replay returns only research-only summary, never order permission",()=>{
 const r=replay.run(fixture());
 assert.equal(r.executionEnabled,false);
 assert.equal(r.assumptions.costDeductions,0);
 assert.equal(r.assumptions.spreadDeductions,0);
 assert.equal(r.assumptions.commissionDeductions,0);
 assert.equal(r.assumptions.slippageDeductions,0);
 assert.equal(r.results.pdf_sweep_bos.executionApproved,false);
});
test("replay makes no inference on unclosed/future OHLC",()=>{
 const f=fixture();
 assert.throws(()=>replay.run({...f,m15:[...f.m15,{...f.m15.at(-1),time:Date.UTC(2026,11,1)}]}),/REPLAY_UNCLOSED_OR_FUTURE_BAR/);
 assert.throws(()=>replay.normalize([...f.m15,f.m15.at(-1)],ms15,asOf),/REPLAY_INVALID/);
});
test("same broker input is deterministic and ignores fake cost fields",()=>{
 const f=fixture(),a=replay.run(f);
 const b=replay.run({...f,m15:f.m15.map(x=>({...x,spread:99,commission:-999,slippage:50})),
  h1:f.h1.map(x=>({...x,swap:-500}))});
 assert.deepEqual(a,b);
});
test("missing broker history and forged OHLC fail closed",()=>{
 const f=fixture();
 assert.throws(()=>replay.run({...f,h1:f.h1.slice(0,20)}),/INSUFFICIENT_MATCHED/);
 assert.throws(()=>replay.normalize(f.m15.map((x,i)=>i===5?{...x,high:-1}:x),ms15,asOf),/REPLAY_INVALID/);
});
test("gross-R drawdown arithmetic is based on actual sequence not win-rate",()=>{
 const r=replay.metrics([{grossR:2,entryTime:base},{grossR:-1,entryTime:base+ms15},{grossR:-1,entryTime:base+2*ms15}]);
 assert.equal(r.trades,3);
 assert.equal(r.wins,1);
 assert.equal(r.totalGrossR,0);
 assert.equal(r.maxDrawdownGrossR,2);
 assert.equal(r.winRatePct,33.33);
});
