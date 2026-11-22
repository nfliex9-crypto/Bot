"use strict";
/**
 * Provenance contract for FUTURE Sentinel V2 demo fills.
 * Converts a verified SQL JOIN (intents + completed broker fills) into the
 * strict purged-forward-evidence input type. No fabricated entry times or risk.
 *
 * Imported historic rows without pre-entry risk or actual broker open_time
 * are intentionally rejected and remain usable only for simple gross P/L.
 * NO trade submission, DB updates, credentials, or simulated cost deductions.
 */
const evidence=require("./purged-forward-evidence.js");
function finite(v){
 if(v===null||v===undefined||v==="")return null;
 const n=Number(v);return Number.isFinite(n)?n:null;
}
function exactDate(v){const t=Date.parse(String(v||""));return Number.isSafeInteger(t)?t:null}
function convert(row){
 if(!row||row.execution_status!=="BROKER_POSITION_OR_HISTORY_CONFIRMED"||
    row.broker_history_complete!==true||row.decision_version===null||
    row.entry_status!=="PREENTRY_RISK_RECORDED"||
    !String(row.account_id||"")||!String(row.broker_ticket||"")||
    !String(row.signal_hash||"")||
    row.family!==row.intent_family||row.symbol!==row.intent_symbol||
    row.side!==row.intent_side||!["LONG","SHORT"].includes(row.side)||
    row.signal_hash!==row.intent_signal_hash)
  return {valid:false,reason:"UNVERIFIED_LEDGER_JOIN"};
 const open=exactDate(row.open_time),close=exactDate(row.close_time),
   tag=exactDate(row.decision_tagged_at);
 const risk=finite(row.risk_at_entry),gross=finite(row.profit);
 if(open===null||close===null||tag===null||!(tag<=open&&open<close)||
    !(risk>0)||gross===null)
  return {valid:false,reason:"MISSING_PREENTRY_OR_BROKER_ENTRY_FACT"};
 return {valid:true,record:{
  accountId:String(row.account_id),ticket:String(row.broker_ticket),
  symbol:row.symbol,family:row.family,isDemo:true,brokerVerified:true,
  complete:true,partial:false,
  openTime:new Date(open).toISOString(),closeTime:new Date(close).toISOString(),
  taggedAt:new Date(tag).toISOString(),
  grossProfit:gross,riskAtEntry:risk
 }};
}
function dataset(rows,{asOf=Date.now(),...options}={}){
 if(!Array.isArray(rows))throw Error("JOINED_LEDGER_REQUIRED");
 const eligible=[],rejectedReasons={};
 for(const r of rows){
  const out=convert(r);
  if(out.valid)eligible.push(out.record);
  else rejectedReasons[out.reason]=(rejectedReasons[out.reason]||0)+1;
 }
 const result=evidence.evaluate(eligible,{asOf,...options});
 return {...result,inputRecords:rows.length,
  eligibleBeforeChronologicalValidation:eligible.length,rejectedReasons,
  accounting:"GROSS_BROKER_PROFIT_NO_EXTRA_DEDUCTIONS",
  source:"VERIFIED_FUSION_DEMO_PREENTRY_LEDGER_JOIN",
  readOnly:true,executionEnabled:false};
}
module.exports={convert,dataset};
