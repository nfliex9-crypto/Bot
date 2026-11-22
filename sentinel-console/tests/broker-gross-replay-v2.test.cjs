"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const {replay}=require("../brain/broker-gross-replay-v2.js");
const now=Date.UTC(2026,10,21,12),M=900000,H=3600000;
function fixture(){
 const m15=Array.from({length:300},(_,i)=>({time:now-(300-i)*M,
  open:100,high:100.1,low:99.9,close:100}));
 const h1=Array.from({length:160},(_,i)=>({time:now-(160-i)*H,
  open:100,high:100.1,low:99.9,close:100}));
 const signalFn=(symbol,m)=>{
  const time=m.at(-1).time;
  if(time!==m15[160].time&&time!==m15[220].time)return null;
  return {symbol,bar_time:time,side:1,family:"pdf_sweep_bos",
   atr:1,stop_atr:1,reward_r:2};
 };
 return {symbol:"XAUUSD",m15,h1,asOf:now,signalFn};
}
test("next-open entry, stop-first ambiguity and independent chronological OOS",()=>{
 const f=fixture();
 f.m15[161]={...f.m15[161],high:103,low:98};
 f.m15[221]={...f.m15[221],high:103};
 const r=replay(f);
 assert.equal(r.train.summary.trades,1,JSON.stringify(r.train));
 assert.equal(r.oos.summary.trades,1,JSON.stringify(r.oos));
 assert.equal(r.train.trades[0].entryTime,f.m15[161].time);
 assert.equal(r.train.trades[0].exitReason,"STOP_FIRST");
 assert.equal(r.train.trades[0].grossR,-1);
 assert.equal(r.oos.trades[0].grossR,2);
 assert.equal(r.costDeductions,0);assert.equal(r.executionEnabled,false);
});
test("adaptive gate can reject a setup or reduce but never exceed approved risk",()=>{
 const f=fixture();
 const a=replay({...f,gateFn:()=>({allowed:false,riskPct:0})});
 assert.equal(a.train.summary.trades,0);assert.equal(a.oos.summary.trades,0);
 const b=replay({...f,gateFn:()=>({allowed:true,riskPct:.1})});
 assert.equal(b.train.trades[0].riskPct,.1);
 assert.throws(()=>replay({...f,gateFn:()=>({allowed:true,riskPct:1})}),
  /RISK_EXCEEDS_AUTHORIZED_CEILING/);
});
test("missing broker candles cannot be silently backfilled",()=>{
 const f=fixture();f.m15.splice(155,1);
 const r=replay(f);
 assert.ok(r.train.skipped.gaps>0);
});
test("adverse opening gaps fill at the observed open, not an optimistic stop price",()=>{
 const f=fixture();
 f.m15[162]={...f.m15[162],open:97,close:97,high:97.1,low:96.9};
 const r=replay(f);
 assert.equal(r.train.trades[0].exitReason,"STOP_FIRST");
 assert.equal(r.train.trades[0].grossR,-3);
});
test("future or malformed candles are rejected before research",()=>{
 const f=fixture();
 assert.throws(()=>replay({...f,asOf:now-1}),/FUTURE_BARS/);
 assert.throws(()=>replay({...f,m15:[...f.m15,f.m15.at(-1)]}),/INVALID_BARS/);
});
