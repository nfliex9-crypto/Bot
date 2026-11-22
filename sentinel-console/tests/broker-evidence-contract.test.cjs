"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const ledger=require("../brain/broker-evidence-contract.js");
const t=Date.UTC(2026,9,10);
function joined(i=0,more={}){
 const open=t+i*86400000;
 return {account_id:"demo_fusion",broker_ticket:"T"+i,
  signal_hash:"h"+i,intent_signal_hash:"h"+i,
  family:"pdf_sweep_bos",intent_family:"pdf_sweep_bos",
  symbol:"EURUSD",intent_symbol:"EURUSD",
  side:"LONG",intent_side:"LONG",
  execution_status:"BROKER_POSITION_OR_HISTORY_CONFIRMED",
  broker_history_complete:true,decision_version:"sentinel-adaptive-intelligence-v2",
  entry_status:"PREENTRY_RISK_RECORDED",
  decision_tagged_at:new Date(open-5000).toISOString(),
  open_time:new Date(open).toISOString(),
  close_time:new Date(open+3600000).toISOString(),
  profit:"25.0",risk_at_entry:"12.5",
  ...more};
}
const opts={asOf:Date.UTC(2026,10,21),minTrain:1,minOos:1,minOosDays:1};
test("verified pre-entry and completed-broker facts convert into gross-R input",()=>{
 const x=ledger.convert(joined());
 assert.equal(x.valid,true);assert.equal(x.record.riskAtEntry,12.5);
 assert.equal(x.record.grossProfit,25);
 assert.equal(x.record.isDemo,true);
});
test("legacy fills without broker openTime or pretrade sizing NEVER become training labels",()=>{
 for(const v of [{open_time:null},{risk_at_entry:null},{decision_tagged_at:null},
  {broker_history_complete:null},{entry_status:"UNKNOWN"},
  {decision_version:null},{execution_status:"RESERVED"},
  {open_time:new Date(t-10000).toISOString()}]){
  assert.equal(ledger.convert(joined(0,v)).valid,false,JSON.stringify(v));
 }
});
test("symbol, family, hash and direction mismatch prevents forged join",()=>{
 for(const v of [{intent_symbol:"BTCUSD"},{intent_family:"pdf_fvg_retest"},
  {intent_signal_hash:"forged"},{intent_side:"SHORT"}]){
  assert.equal(ledger.convert(joined(0,v)).valid,false,JSON.stringify(v));
 }
});
test("complete tagged fills become purged OOS research only, never demo auto-approval",()=>{
 const rows=Array.from({length:60},(_,i)=>joined(i));
 const r=ledger.dataset(rows,opts);
 assert.equal(r.eligibleBeforeChronologicalValidation,60);
 assert.equal(r.accepted,60);assert.equal(r.ordersEnabled,false);
 assert.equal(r.executionEnabled,false);
 assert.equal(r.strategies[0].train.trades,39);
 assert.equal(r.strategies[0].oos.trades,21);
 assert.equal(r.costDeductions,0);
});
test("broker swap/commission ignored in gross R but never rewritten",()=>{
 const a=Array.from({length:40},(_,i)=>joined(i));
 const b=a.map(x=>({...x,swap:"-100",commission:"-2000"}));
 assert.deepEqual(ledger.dataset(a,opts),ledger.dataset(b,opts));
});
