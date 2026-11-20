"use strict";
/**
 * AMT Bootcamp source registry and educational-data gate for Sentinel.
 * User supplied 14 URL IDs on 2026-11-20.
 *
 * The owner-provided videos' accessible English caption tracks were inspected
 * with vidIQ on 2026-11-20; auto-captions and visual explanations are
 * NOT independently verified. Only short, original, timestamped research
 * notes are stored, not the copyrighted full transcripts.
 * No source or inferred rule can authorize a brokerage order.
 */
const crypto=require("node:crypto");
const IDS=Object.freeze([
 "z4Lq1IGmrS8","dqONJMI1rYM","LwDarLLYg8w","mQ45-sOiQ24",
 "9Ikd_J41kGw","YNersT1IG9s","I-6yE7UtJ5U","M4b8WVfqDtM",
 "ddp6ZIqmaOc","sZhdaMr-fFY","8jtLFS7ZJxo","nLCeDXzJiI8",
 "GeWGu7mBvIc","7HXYhinEkRI"
]);
const TITLES=Object.freeze([
 "Session 1 Q&A with Andrea Cimi",
 "Session 2 Orderflow Bootcamp with Fabio Valentini",
 "Session 3 Q&A with Andrea Cimi",
 "Session 4 Orderflow Bootcamp with Fabio Valentini",
 "Session 5 Q&A with Andrea Cimi",
 "Session 6 Orderflow Bootcamp with Fabio Valentini",
 "Session 7 Q&A with Andrea Cimi",
 "Session 8 Orderflow Bootcamp with Fabio Valentini",
 "Session 9 Orderflow with Fabio Valentini",
 "Session 10 Orderflow with Andrea Cimi",
 "Session 11 Orderflow with Andrea Cimi",
 "Session 12 Orderflow with Fabio Valentini",
 "Session 13 Orderflow with Fabio Valentini",
 "Session 14 Orderflow with Fabio Valentini"
]);
const CAPTION_EVIDENCE=Object.freeze([
 {id:IDS[0],seconds:2127,concept:"auction_balance",note:"Session value-area levels contextualize the auction; real volume-at-price is necessary for genuine VAH and VAL."},
 {id:IDS[1],seconds:311,concept:"auction_balance",note:"A directional auction can flip through an earlier point of control and leave the previous balance."},
 {id:IDS[2],seconds:2604,concept:"failed_auction",note:"After breakout, a pullback to the participating order-flow imbalance cluster can be an entry hypothesis; footprint data is required to confirm that cluster."},
 {id:IDS[3],seconds:1002,concept:"failed_auction",note:"Compare effort and achieved price result when one side fails and the other drives the auction."},
 {id:IDS[4],seconds:3174,concept:"auction_balance",note:"Avoid assuming directional edge in the middle of a range where price oscillates."},
 {id:IDS[5],seconds:805,concept:"auction_balance",note:"Form a market narrative using direction, location and timing rather than an isolated candle."},
 {id:IDS[6],seconds:2782,concept:"failed_auction",note:"Evaluate failed auction at a range boundary rather than automatically chasing every breakout."},
 {id:IDS[7],seconds:3484,concept:"failed_auction",note:"The close back into a value area distinguishes acceptance from a rejection attempt."},
 {id:IDS[8],seconds:1155,concept:"failed_auction",note:"A level break that fails on subsequent price action calls for context, not an immediate mechanical entry."},
 {id:IDS[9],seconds:3696,concept:"delta_absorption",note:"Failed auction examples distinguish low-aggression exhaustion from absorption supported by footprint evidence."},
 {id:IDS[10],seconds:303,concept:"auction_balance",note:"Define higher-timeframe directional bias, then wait for range failure or successful breakout confirmation."},
 {id:IDS[11],seconds:2099,concept:"delta_absorption",note:"Large order-flow effort without matching price movement is proposed as evidence to investigate, not proof of future direction."},
 {id:IDS[12],seconds:3058,concept:"delta_absorption",note:"Session control can be assessed from actual aggressive buying and selling; broker OHLC alone cannot verify this."},
 {id:IDS[13],seconds:6351,concept:"auction_balance",note:"Price accepting progressively higher auction levels can suggest a regime transition requiring confirmation."}
].map(x=>Object.freeze({...x,review:"CAPTION_PARAPHRASE_UNVERIFIED",orders_authorized:false,
 source_url:"https://www.youtube.com/watch?v="+x.id+"&t="+x.seconds+"s"})));
const SOURCE_CATALOG=Object.freeze(IDS.map((id,i)=>Object.freeze({
 id,order:i+1,url:"https://www.youtube.com/watch?v="+id,
 title:TITLES[i],submitted_by:"owner",content_status:"CAPTIONS_RETRIEVED_UNREVIEWED",
 captions_accessible:true,captions_language:"en",caption_accessed_on:"2026-11-20",
 video_verified:false,transcript_verified:false,notes_verified:false,
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
  if(!/^[A-Za-z0-9_-]{11}$/.test(s.id)||!s.url.endsWith(s.id)||s.content_status!=="CAPTIONS_RETRIEVED_UNREVIEWED"||s.captions_accessible!==true||
     s.orders_authorized!==false)throw Error("INVALID_SOURCE_OR_STATUS");
 }
 return true;
}
function curriculumStatus(feed=DEMO_FEED){
 return {
  linked_sources:SOURCE_CATALOG.length,
  content_read:SOURCE_CATALOG.length,captions_accessible:SOURCE_CATALOG.length,
  transcript_language:"en",transcripts_verified:0,video_specific_claims:0,
  timestamped_research_notes:CAPTION_EVIDENCE.length,
  reviewed_research_rules:0,
  auto_train_model:false,autonomous_broker_orders:false,
  state:"CAPTIONS_RETRIEVED_RULES_UNREVIEWED",
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
module.exports={IDS,TITLES,SOURCE_CATALOG,CAPTION_EVIDENCE,CONCEPTS,DEMO_FEED,validateCatalog,
  curriculumStatus,stageTranscript,proposedRule};
