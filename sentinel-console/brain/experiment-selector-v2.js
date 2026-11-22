"use strict";
/**
 * Sentinel V2 research tournament: pre-tagged, verified DEMO fills only.
 * Each candidate is evaluated on purged, chronological OOS day blocks.
 * An explicit screened-hypotheses ledger is needed before research priority.
 * NEVER changes execution settings, account risk or broker orders.
 */
const evidence=require("./purged-forward-evidence.js");
const {blockBootstrap}=require("./robustness.js");
const VERSION="sentinel-v2-experiment-selector-1";
const finite=x=>typeof x==="number"&&Number.isFinite(x);
function select(input,{asOf=Date.now(),trainFraction=.65,embargoMs=3600000,
 minTrain=20,minOos=20,minOosDays=12,hypothesesScreened=null,
 screeningLedgerVerified=false,resamples=512}={}){
 if(!Array.isArray(input)||!Number.isSafeInteger(asOf)||!finite(trainFraction)||
   trainFraction<=.4||trainFraction>=.9||!Number.isSafeInteger(embargoMs)||embargoMs<0||
   !Number.isSafeInteger(minTrain)||minTrain<1||!Number.isSafeInteger(minOos)||minOos<1||
   !Number.isSafeInteger(minOosDays)||minOosDays<4)
  throw Error("INVALID_TOURNAMENT_INPUT");
 const baseline=evidence.evaluate(input,{asOf,trainFraction,embargoMs,minTrain,minOos,minOosDays});
 const grouped=new Map(),seen=new Set();
 for(const row of input){
  const checked=evidence.record(row,asOf);
  if(!checked.valid)continue;
  const r=checked.row,identity=r.accountId+"|"+r.ticket;
  if(seen.has(identity))continue;
  seen.add(identity);
  const key=JSON.stringify([r.accountId,r.symbol,r.family]);
  const group=grouped.get(key)||[];group.push(r);grouped.set(key,group);
 }
 const count=grouped.size;
 const ledgerValid=screeningLedgerVerified===true&&Number.isInteger(hypothesesScreened)&&
  hypothesesScreened>=count&&hypothesesScreened<=100;
 const testCount=ledgerValid?hypothesesScreened:Math.max(1,Math.min(100,count));
 const strategies=[];
 for(const [key,rows] of grouped){
  rows.sort((a,b)=>a.open-b.open||a.close-b.close||a.ticket.localeCompare(b.ticket));
  const at=Math.max(1,Math.floor(rows.length*trainFraction));
  const boundary=rows[at]?.open;
  const train=rows.slice(0,at).filter(x=>!boundary||x.close+embargoMs<=boundary);
  const oos=rows.slice(at);
  const [accountId,symbol,family]=JSON.parse(key);
  const match=baseline.strategies.find(x=>x.accountId===accountId&&x.symbol===symbol&&x.family===family);
  if(!match||match.train.trades!==train.length||match.oos.trades!==oos.length)
   throw Error("PURGED_EVIDENCE_SPLIT_MISMATCH");
  const robust=blockBootstrap(oos.map(x=>({entryTime:x.open,rr:x.r})),{
   strategyId:key,strategyCount:testCount,minDays:Math.max(4,Math.min(200,minOosDays)),resamples});
  const enough=train.length>=minTrain&&oos.length>=minOos&&robust.sample_days>=minOosDays;
  const positiveTrain=match.train.expectancyR!==null&&match.train.expectancyR>0;
  const robustOos=robust.eligible_for_paper_research===true;
  const priority=enough&&ledgerValid&&positiveTrain&&robustOos;
  const status=!enough?"NEEDS_MORE_VERIFIED_FORWARD_DATA":
   !ledgerValid?"SCREENING_LEDGER_UNVERIFIED":
   priority?"RESEARCH_PRIORITY_FOR_MANUAL_REVIEW":"REJECT_OR_REWORK";
  strategies.push({accountId,symbol,family,status,
   train:match.train,oos:match.oos,purgedTrainTrades:match.purgedTrainTrades,
   bootstrap:{sampleDays:robust.sample_days,lowerBoundDailyMeanR:robust.lower_bound_r,
    adjustedOneSidedAlpha:robust.adjusted_one_sided_alpha,
    screenedHypotheses:testCount,method:robust.method},
   researchPriority:priority?2:status==="REJECT_OR_REWORK"?0:1,
   executionApproved:false,promotedToDemo:false,executionEnabled:false,
   reason:status==="RESEARCH_PRIORITY_FOR_MANUAL_REVIEW"?
    "POSITIVE_PURGED_OOS_DAY_BLOCK_BOUND_REQUIRES_INDEPENDENT_REVIEW":status});
 }
 strategies.sort((a,b)=>b.researchPriority-a.researchPriority||
   a.accountId.localeCompare(b.accountId)||a.symbol.localeCompare(b.symbol)||
   a.family.localeCompare(b.family));
 return {version:VERSION,screeningLedgerVerified:ledgerValid,
  screenedHypotheses:ledgerValid?hypothesesScreened:null,
  accepted:baseline.accepted,rejected:baseline.rejected,
  candidateFamilies:count,strategies,executionEnabled:false,
  autoPromotion:false,costDeductions:0,
  note:"Research-only gross R; multiple-testing ledger is required, not assumed."};
}
module.exports={VERSION,select};
