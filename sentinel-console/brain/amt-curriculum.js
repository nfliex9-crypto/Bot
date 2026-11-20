"use strict";
/**
 * AMT Bootcamp source registry and educational-data gate for Sentinel.
 * User supplied 14 URL IDs on 2026-11-20.
 *
 * No captions were available at registration time. The list is not a
 * transcription, summary, endorsement or attribution of any lesson.
 * No source or inferred rule can authorize a brokerage order.
 */
const crypto=require("node:crypto");
const captionEvidence=require("./amt-evidence.js");
const IDS=Object.freeze([
 "z4Lq1IGmrS8","dqONJMI1rYM","LwDarLLYg8w","mQ45-sOiQ24",
 "9Ikd_J41kGw","YNersT1IG9s","I-6yE7UtJ5U","M4b8WVfqDtM",
 "ddp6ZIqmaOc","sZhdaMr-fFY","8jtLFS7ZJxo","nLCeDXzJiI8",
 "GeWGu7mBvIc","7HXYhinEkRI"
]);
const SOURCE_CATALOG=Object.freeze(IDS.map((id,i)=>Object.freeze({
 id,order:i+1,url:"https://www.youtube.com/watch?v="+id,
 title:"Bootcamp — episode "+(i+1)+" (title not verified)",
 submitted_by:"owner",content_status:"TIMECODED_CAPTIONS_INDEXED_UNAUDITED",
 video_verified:false, transcript_verified:false,notes_verified:false,
 captions_indexed:captionEvidence.INDEX.get(id)?.caption_accessed===true,
 evidence_anchors:captionEvidence.INDEX.get(id)?.anchors||[],
 orders_authorized:false
})));
const SOURCE_SET=new Set(IDS);
/**
 * Concept families are independently proposed research directions sourced
 * from broader AMT knowledge. They are NOT video-specific quotes/conclusions.
 */
const CONCEPTS=Object.freeze([
 Object.freeze({id:"auction_balance",label:"Balanced vs imbalanced auction",
  required:["broker_ohlc","session_calendar"],intent:"MARKET_REGIME_ONLY",
  data_caveat:"Price-area approximation, not a verified Volume Profile"}),
 Object.freeze({id:"failed_auction",label:"Failed auction and level rejection",
  required:["broker_ohlc","bid_ask_quote"],intent:"SHADOW_SIGNAL_ONLY",
  data_caveat:"OHLC proxy for failed auction; not evidence of aggressive trades"}),
 Object.freeze({id:"opening_range",label:"Opening range and acceptance / rejection",
  required:["broker_ohlc","session_calendar"],intent:"SHADOW_SIGNAL_ONLY",
  data_caveat:"Sessions and DST must match instrument exchange"}),
 Object.freeze({id:"volume_profile",label:"VAH / VAL / POC / LVN from volume-at-price",
  required:["volume_at_price"],intent:"DATA_BLOCKED",
  data_caveat:"MT5 tick volume is not consolidated volume-at-price"}),
 Object.freeze({id:"delta_absorption",label:"Delta, CVD and absorption",
  required:["aggressor_side_trades"],intent:"DATA_BLOCKED",
  data_caveat:"Cannot infer genuine aggressive-volume delta from OHLC"}),
 Object.freeze({id:"iceberg_reload",label:"Iceberg / reload / book flip",
  required:["depth_l2","market_by_order","aggressor_side_trades"],intent:"DATA_BLOCKED",
  data_caveat:"Requires compatible exchange order book and tape; spot MT5 insufficient"})
]);
const DEMO_FEED=Object.freeze({
 broker_ohlc:true,bid_ask_quote:true,
 session_calendar:false, // requires instrument-specific verified sessions
 volume_at_price:false,aggressor_side_trades:false,
 depth_l2:false,market_by_order:false
});
function validateCatalog(){
 if(SOURCE_CATALOG.length!==14||SOURCE_SET.size!==14)throw Error("INVALID_BOOTCAMP_CATALOG");
 for(const s of SOURCE_CATALOG){
  if(!/^[A-Za-z0-9_-]{11}$/.test(s.id)||!s.url.endsWith(s.id)||s.content_status!=="TIMECODED_CAPTIONS_INDEXED_UNAUDITED"||
     s.captions_indexed!==true||
     s.orders_authorized!==false)throw Error("INVALID_SOURCE_OR_STATUS");
 }
 return captionEvidence.validate();
}
function curriculumStatus(feed=DEMO_FEED){
 return {
  linked_sources:SOURCE_CATALOG.length,
  captions_indexed:captionEvidence.EVIDENCE.length,
  caption_evidence_leads:captionEvidence.EVIDENCE.reduce((n,e)=>n+e.anchors.length,0),
  content_read:0,transcripts_verified:0,video_specific_claims:0,
  auto_train_model:false,autonomous_broker_orders:false,
  state:"TIMECODED_CAPTIONS_INDEXED_UNAUDITED",
  concept_research:CONCEPTS.map(c=>{
   const missing=c.required.filter(k=>feed[k]!==true);
   return {id:c.id,label:c.label,status:missing.length?"DATA_UNAVAILABLE":"RESEARCH_DATA_PRESENT_SOURCE_UNVERIFIED",
     missing_inputs:missing,intent:c.intent,notice:c.data_caveat,
     video_attribution_verified:false,execution_enabled:false};
  })
 };
}
/**
 * Staging: consume timestamps provided by a connected transcript service or
 * by the owner; return only an aggregate fingerprint and bounded snippet refs.
 * No large copyrighted subtitle dump is committed to the Git repository.
 */
function stageTranscript({videoId,segments,origin}){
 if(!SOURCE_SET.has(videoId))throw Error("SOURCE_NOT_IN_BOOTCAMP");
 if(!["OWNER_SUPPLIED","AUTHORIZED_CAPTIONS"].includes(origin))throw Error("TRANSCRIPT_PROVENANCE_REQUIRED");
 if(!Array.isArray(segments)||segments.length<1||segments.length>20000)throw Error("INVALID_CAPTION_SEGMENTS");
 let prev=-1,total=0;
 const normalized=segments.map(x=>{
  const at=Number(x?.seconds),str=String(x?.text||"").trim();
  if(!Number.isFinite(at)||at<0||at<prev||str.length<1||str.length>1200)throw Error("INVALID_TIMESTAMPS_OR_TEXT");
  total+=str.length;prev=at;
  if(total>350000)throw Error("TRANSCRIPT_TOO_LARGE");
  return {at,text:str};
 });
 const checksum=crypto.createHash("sha256")
   .update(JSON.stringify({videoId,origin,normalized})).digest("hex");
 return {videoId,origin,caption_segments:normalized.length,sha256:checksum,
  content_status:"TRANSCRIPT_STAGED_UNREVIEWED",
  fact_extraction_required:true,video_verified:false,
  evidence_quote_limit_chars:120,publication_disabled:true,
  auto_promotion:false,orders_authorized:false};
}
function proposedRule({conceptId,sourceId,evidenceTimestampSeconds,transcriptSha,rule}={}){
 const known=CONCEPTS.find(x=>x.id===conceptId);
 if(!known||!SOURCE_SET.has(sourceId)||!Number.isFinite(evidenceTimestampSeconds)||
   evidenceTimestampSeconds<0||!/^[a-f0-9]{64}$/.test(transcriptSha||"")||
   typeof rule!=="string"||rule.trim().length<15||rule.length>1000)
   throw Error("EVIDENCE_REQUIRED_FOR_PROPOSED_RULE");
 return {conceptId,sourceId,evidenceTimestampSeconds,transcriptSha,rule:rule.trim(),
  review_status:"HUMAN_AND_RESEARCH_VALIDATION_REQUIRED",
  data_requirements:[...known.required],proven_in_backtest:false,
  proven_out_of_sample:false,forward_evidence:0,approved_for_execution:false};
}
module.exports={IDS,SOURCE_CATALOG,CONCEPTS,DEMO_FEED,validateCatalog,
  curriculumStatus,stageTranscript,proposedRule};
