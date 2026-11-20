"use strict";
const test=require("node:test"),assert=require("node:assert/strict");
const weekly=require("../worker/cloud-trader/weekly-selector.js");
const pdf=require("../worker/cloud-trader/source-signals.js");
const c=require("../worker/cloud-trader/core.js");
const now=Date.UTC(2026,10,20,12);
function trade(family,day,pnl,fee=0,symbol="XAUUSD"){
 return {family,symbol,closeTime:day+"T18:00:00Z",profit:pnl,swap:0,
  commission:fee,complete:true,brokerVerified:true};
}
function sample(family,winner,symbol="XAUUSD"){
 const before=["2026-10-27","2026-10-29","2026-11-02","2026-11-04","2026-11-06","2026-11-07"];
 const week=["2026-11-09","2026-11-11","2026-11-14"];
 const entries=[];
 for(let i=0;i<12;i++)entries.push(trade(family,before[i%6],winner?(i%6===0?-5:14):(i%6===0?4:-18),0,symbol));
 for(let i=0;i<6;i++)entries.push(trade(family,week[i%3],winner?(i===0?-10:20):(i===0?6:-22),0,symbol));
 return entries;
}
test("weekly review starts after completed UTC calendar week",()=>{
 assert.deepEqual(weekly.windowAt(now),{weekStart:"2026-11-09",
  weekEnd:"2026-11-16T00:00:00.000Z",
  lookbackStart:"2026-10-19T00:00:00.000Z"});
 assert.equal(weekly.windowAt(Date.UTC(2026,10,23,1)).weekStart,"2026-11-16");
});
test("broker-verified outcomes pause qualified loser and reward qualified winner",()=>{
 const profiles=weekly.evaluate([...sample("pdf_sweep_bos",false),
  ...sample("pdf_fvg_retest",true)],{symbol:"XAUUSD",now}).profiles;
 assert.equal(profiles.find(x=>x.family==="pdf_sweep_bos").status,"PAUSED_LOSING");
 assert.equal(profiles.find(x=>x.family==="pdf_sweep_bos").priority,0);
 assert.equal(profiles.find(x=>x.family==="pdf_fvg_retest").status,"REWARDED_PRIORITY");
 assert.equal(profiles.find(x=>x.family==="pdf_fvg_retest").priority,2);
});
test("two recent losses never cause deletion, even if PnL negative",()=>{
 const p=weekly.evaluate([trade("pdf_sweep_bos","2026-11-12",-20),
  trade("pdf_sweep_bos","2026-11-13",-50)],{symbol:"XAUUSD",now});
 assert.equal(p.profiles.find(x=>x.family==="pdf_sweep_bos").priority,1);
 assert.equal(p.profiles.find(x=>x.family==="pdf_sweep_bos").status,"COLLECTING");
});
test("bad or unverified records must not be treated as real broker fills",()=>{
 assert.throws(()=>weekly.evaluate([{...trade("pdf_fvg_retest","2026-11-12",10),brokerVerified:false}],
  {symbol:"XAUUSD",now}),/UNVERIFIED/);
 assert.throws(()=>weekly.evaluate([{...trade("pdf_fvg_retest","2026-11-12",10),commission:null}],
  {symbol:"XAUUSD",now}),/INCOMPLETE/);
});
test("scoring uses net fees and correct symbol",()=>{
 const x=[trade("pdf_sweep_bos","2026-11-12",10,-15),
          trade("pdf_fvg_retest","2026-11-12",500,0,"BTCUSD")];
 const p=weekly.evaluate(x,{symbol:"XAUUSD",now});
 assert.equal(p.profiles.find(x=>x.family==="pdf_sweep_bos").week.net,-5);
 assert.equal(p.profiles.find(x=>x.family==="pdf_fvg_retest").week.trades,0);
});
test("source selector refuses paused family and never increases per-trade risk",()=>{
 assert.deepEqual(weekly.policyFromScores([{symbol:"XAUUSD",family:"pdf_sweep_bos",
  priority:0,status:"PAUSED_LOSING"},{symbol:"XAUUSD",family:"pdf_fvg_retest",
  priority:2,status:"REWARDED_PRIORITY"}],"XAUUSD"),{pdf_sweep_bos:0,pdf_fvg_retest:2});
 assert.equal(pdf.RULES.pdf_sweep_bos.stop_atr,1.7);
 assert.equal(pdf.RULES.pdf_fvg_retest.stop_atr,1.5);
 assert.equal(c.demoExecutionAllowed({}, {id:"demo",broker:"mt5",isDemo:true,hot:true}),false);
});
