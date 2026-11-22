"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const {select}=require("../brain/experiment-selector-v2.js");
const base=Date.UTC(2026,6,1),DAY=86400000,asOf=Date.UTC(2026,10,22);
function fill(i,overrides={}){
 const open=base+i*DAY;
 return {accountId:"fusion-demo",ticket:"T"+i,symbol:"XAUUSD",
  family:"pdf_sweep_bos",isDemo:true,brokerVerified:true,
  complete:true,partial:false,
  openTime:new Date(open).toISOString(),
  closeTime:new Date(open+3600000).toISOString(),
  taggedAt:new Date(open-900000).toISOString(),
  grossProfit:10,riskAtEntry:10,...overrides};
}
const ledger={asOf,screeningLedgerVerified:true,hypothesesScreened:8};
test("strong verified training and OOS days receive research priority, never broker permission",()=>{
 const x=select(Array.from({length:100},(_,i)=>fill(i)),ledger);
 assert.equal(x.strategies.length,1);
 assert.equal(x.strategies[0].status,"RESEARCH_PRIORITY_FOR_MANUAL_REVIEW",JSON.stringify(x));
 assert.equal(x.strategies[0].train.trades,65);
 assert.equal(x.strategies[0].oos.trades,35);
 assert.ok(x.strategies[0].bootstrap.lowerBoundDailyMeanR>0);
 assert.equal(x.strategies[0].executionApproved,false);
 assert.equal(x.executionEnabled,false);
 assert.equal(x.autoPromotion,false);
 assert.equal(x.costDeductions,0);
});
test("OOS deterioration rejects even when training was excellent",()=>{
 const rows=Array.from({length:100},(_,i)=>fill(i,{grossProfit:i>=65?-10:30}));
 const x=select(rows,ledger).strategies[0];
 assert.equal(x.status,"REJECT_OR_REWORK");
 assert.ok(x.oos.expectancyR<0);
 assert.equal(x.researchPriority,0);
});
test("without a verified record of ALL screened hypotheses no promotion of research priority",()=>{
 const rows=Array.from({length:100},(_,i)=>fill(i));
 const x=select(rows,{asOf});
 assert.equal(x.screeningLedgerVerified,false);
 assert.equal(x.strategies[0].status,"SCREENING_LEDGER_UNVERIFIED");
 assert.equal(x.strategies[0].researchPriority,1);
 assert.equal(select(rows,{...ledger,hypothesesScreened:0}).screeningLedgerVerified,false);
});
test("few trades or days cannot establish a robust forward edge",()=>{
 const rows=Array.from({length:25},(_,i)=>fill(i));
 const x=select(rows,ledger);
 assert.equal(x.strategies[0].status,"NEEDS_MORE_VERIFIED_FORWARD_DATA");
 assert.equal(x.strategies[0].researchPriority,1);
});
test("rejects forged, duplicated, future or untagged trades",()=>{
 const rows=[...Array.from({length:100},(_,i)=>fill(i)),
  fill(0,{grossProfit:999}),fill(101,{brokerVerified:false}),
  fill(102,{taggedAt:new Date(base+103*DAY).toISOString()}),
  fill(103,{closeTime:"2027-01-01T00:00:00.000Z"})];
 const x=select(rows,ledger);
 assert.equal(x.accepted,100);assert.equal(x.rejected,4);
 assert.equal(x.strategies[0].oos.trades,35);
});
test("strategy tournament isolates account, symbol and family",()=>{
 const a=Array.from({length:90},(_,i)=>fill(i));
 const b=Array.from({length:90},(_,i)=>fill(i,{accountId:"another-demo",
  symbol:"BTCUSD",family:"pdf_fvg_retest"}));
 const x=select([...a,...b],{...ledger,hypothesesScreened:2});
 assert.equal(x.candidateFamilies,2);
 assert.equal(x.strategies.length,2);
 assert.ok(x.strategies.every(z=>z.status==="RESEARCH_PRIORITY_FOR_MANUAL_REVIEW"));
 assert.ok(x.strategies.every(z=>z.executionApproved===false));
});
test("chronological ranking is deterministic despite shuffled input",()=>{
 const a=Array.from({length:100},(_,i)=>fill(i,{grossProfit:i%3===0?-5:15}));
 assert.deepEqual(select(a,ledger),select([...a].reverse(),ledger));
});
