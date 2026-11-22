"use strict";
/**
 * Sentinel V2: research-only, account-isolated, purged chronological evidence.
 *
 * Rejections are explicit. A completed trade only enters the sample if its
 * strategy was tagged BEFORE entry and its entry-risk was verified. The
 * early (training) trade whose outcome overlaps the start of the later
 * out-of-sample window is PURGED, with an additional embargo. Thus neither
 * training nor strategy evaluation can learn a future OOS outcome.
 *
 * Gross broker profit / verified entry-risk; NO synthetic deductions.
 * This module never sends orders or promotes strategies to execution.
 */
const VERSION="sentinel-purged-forward-evidence-v1";
const FAMILIES=new Set(["pdf_sweep_bos","pdf_fvg_retest",
  "sweep_divergence_bos","trend_delta_surge"]);
const time=x=>{
 const n=typeof x==="number"?x:Date.parse(String(x??""));
 return Number.isSafeInteger(n)?n:NaN;
};
const finite=x=>typeof x==="number"&&Number.isFinite(x);
const round=(x,n=4)=>Number(x.toFixed(n));
function record(row,asOf){
 const open=time(row?.openTime),close=time(row?.closeTime),tag=time(row?.taggedAt);
 if(row?.isDemo!==true||row?.brokerVerified!==true||row?.complete!==true||
    row?.partial===true||typeof row?.ticket!=="string"&&!Number.isSafeInteger(row?.ticket)||
    !String(row?.ticket??"").trim()||!String(row?.accountId??"").trim()||
    typeof row?.symbol!=="string"||!/^[A-Za-z0-9._#-]{2,24}$/.test(row.symbol)||
    !FAMILIES.has(row?.family)||!finite(row?.grossProfit)||
    !finite(row?.riskAtEntry)||row.riskAtEntry<=0||
    !Number.isFinite(open)||!Number.isFinite(close)||!Number.isFinite(tag)||
    !(tag<=open&&open<close&&close<=asOf))
   return {valid:false,reason:"UNVERIFIED_OR_LEAKING_TRADE"};
 const r=row.grossProfit/row.riskAtEntry;
 if(!Number.isFinite(r))return {valid:false,reason:"INVALID_GROSS_R"};
 return {valid:true,row:{accountId:String(row.accountId),ticket:String(row.ticket),
  symbol:row.symbol,family:row.family,open,close,tag,r}};
}
function stats(rows){
 const values=rows.map(x=>x.r);
 let gain=0,loss=0,equity=0,peak=0,maxDrawdown=0;
 for(const r of values){
  if(r>0)gain+=r;else loss-=r;
  equity+=r;peak=Math.max(peak,equity);maxDrawdown=Math.max(maxDrawdown,peak-equity);
 }
 return {trades:values.length,
  winPct:values.length?round(values.filter(x=>x>0).length/values.length*100,2):null,
  expectancyR:values.length?round(equity/values.length):null,
  profitFactor:loss?round(gain/loss):null,
  grossTotalR:round(equity),maxDrawdownR:round(maxDrawdown),
  days:new Set(rows.map(x=>new Date(x.close).toISOString().slice(0,10))).size};
}
function evaluate(input,{asOf=Date.now(),trainFraction=.65,embargoMs=3600000,
                     minTrain=20,minOos=15,minOosDays=5}={}){
 if(!Array.isArray(input))throw Error("BROKER_TRADES_EXPECTED");
 if(!Number.isSafeInteger(asOf)||!Number.isFinite(trainFraction)||
    !(trainFraction>.4&&trainFraction<.9)||!Number.isSafeInteger(embargoMs)||
    embargoMs<0||!Number.isSafeInteger(minTrain)||minTrain<1||
    !Number.isSafeInteger(minOos)||minOos<1||
    !Number.isSafeInteger(minOosDays)||minOosDays<1)
  throw Error("INVALID_EVIDENCE_OPTIONS");
 const groups=new Map(),seen=new Set();let rejected=0;
 for(const candidate of input){
  const out=record(candidate,asOf);
  if(!out.valid){rejected++;continue}
  const r=out.row,identity=r.accountId+"|"+r.ticket;
  if(seen.has(identity)){rejected++;continue}
  seen.add(identity);
  const key=JSON.stringify([r.accountId,r.symbol,r.family]);
  const g=groups.get(key)||[];g.push(r);groups.set(key,g);
 }
 const strategies=[];
 for(const [key,rows] of groups){
  rows.sort((a,b)=>a.open-b.open||a.close-b.close||a.ticket.localeCompare(b.ticket));
  const at=Math.max(1,Math.floor(rows.length*trainFraction));
  const boundary=rows[at]?.open;
  const [accountId,symbol,family]=JSON.parse(key);
  // Keep only observations that will have been closed and settled before
  // OOS starts. Purged trade outcomes must NEVER appear in either split.
  const initial=rows.slice(0,at),oos=rows.slice(at);
  const train=oos.length?initial.filter(x=>x.close+embargoMs<=boundary):initial;
  const purged=initial.length-train.length;
  const tr=stats(train),os=stats(oos);
  const enough=tr.trades>=minTrain&&os.trades>=minOos&&os.days>=minOosDays;
  const promising=enough&&tr.expectancyR>0&&os.expectancyR>0;
  strategies.push({accountId,symbol,family,train:tr,oos:os,
   status:!enough?"COLLECTING_FORWARD":promising?
     "PROMISING_REQUIRES_INDEPENDENT_REVIEW":"WEAK_OR_UNSTABLE",
   purgedTrainTrades:purged,
   firstOosOpen:oos.length?new Date(boundary).toISOString():null,
   lastTrainClose:train.length?new Date(Math.max(...train.map(x=>x.close))).toISOString():null,
   embargoMs,executionApproved:false,promotedToDemo:false,
   explanation:enough?"Purged chronological gross forward review":
     "Insufficient isolated, pretagged, purged training or OOS evidence"});
 }
 strategies.sort((a,b)=>a.accountId.localeCompare(b.accountId)||
   a.symbol.localeCompare(b.symbol)||a.family.localeCompare(b.family));
 return {version:VERSION,records:input.length,accepted:seen.size,rejected,strategies,
  split:"PURGED_CHRONOLOGICAL_"+Math.round(trainFraction*100)+"_"+Math.round((1-trainFraction)*100),
  embargoMs,costDeductions:0,ordersEnabled:false};
}
module.exports={VERSION,FAMILIES,record,stats,evaluate};
