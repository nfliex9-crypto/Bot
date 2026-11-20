"use strict";
/**
 * AMT Bootcamp caption-evidence index. The 14 user-provided video IDs were
 * queried using vidIQ's English timecoded transcript service (2026-11-20).
 * These are short paraphrased topic pointers, not transcripts or validated
 * trade rules. Automatic captions can be inaccurate; no audio audit performed.
 */
const EVIDENCE=Object.freeze([
 {id:"z4Lq1IGmrS8",anchors:[["07:05","L1 vs L2 market data; footprints and depth have different feed needs"],["34:38","Daily session volume profile and contextual price areas"]]},
 {id:"dqONJMI1rYM",anchors:[["05:26","Leaving the value area and searching for a new balance"],["01:01:48","Delta profile is used to compare activity across price levels"]]},
 {id:"LwDarLLYg8w",anchors:[["11:06","Failed auction: price returns inside a longer-term area"],["13:07","Opening range breakout setup with an early session range"]]},
 {id:"mQ45-sOiQ24",anchors:[["03:35","Value-area boundary as a potential protection level"],["01:02:25","Acceptance versus rejection around the value area"]]},
 {id:"9Ikd_J41kGw",anchors:[["14:18","Opening range breakout requires confirmation"],["15:47","Failed auction and rejection with participation context"]]},
 {id:"YNersT1IG9s",anchors:[["04:59","Previous session value area as context"],["44:46","Absorption and sell-side delta as a market interaction"]]},
 {id:"I-6yE7UtJ5U",anchors:[["03:49","Absorption and initiative selling as potential confirmation"],["06:18","Delta and absorption shown using the trade tape"]]},
 {id:"M4b8WVfqDtM",anchors:[["05:52","Cash-session volume profile and rejection areas"],["01:10:42","Fixed profile across a swing or session"]]},
 {id:"ddp6ZIqmaOc",anchors:[["42:52","Failed auction at accumulation boundary"],["51:12","Compare delta effort against resulting price movement"]]},
 {id:"sZhdaMr-fFY",anchors:[["18:02","Opening-range breakout and nearby value-area boundaries"],["01:01:36","Failed-auction variations: exhaustion and strong counterpressure"]]},
 {id:"8jtLFS7ZJxo",anchors:[["05:03","Trend bias followed by a balance/range context"],["07:49","Range-based failed-auction or breakout setup choices"]]},
 {id:"nLCeDXzJiI8",anchors:[["34:59","Failed auction discussed in terms of effort and outcome"],["48:50","Price returning into a value area after a failed move"]]},
 {id:"GeWGu7mBvIc",anchors:[["50:58","Session buyers-versus-sellers control assessment"],["01:02:14","Price-only initial balance contrasted with volume-based context"]]},
 {id:"7HXYhinEkRI",anchors:[["01:27:31","Buy-side effort failing to advance: absorption discussion"],["01:45:51","Auction moving higher as a possible regime change"]]}
].map(x=>Object.freeze({id:x.id,transcript_provider:"vidIQ",language:"en",
 caption_accessed:true,audio_verified:false,caption_qa_status:"TIMECODED_CAPTIONS_INDEXED_UNAUDITED",
 anchors:Object.freeze(x.anchors.map(([timestamp,topic])=>Object.freeze({timestamp,topic,
  video_specific_strategy_validated:false,execution_enabled:false})))
})));
const INDEX=new Map(EVIDENCE.map(x=>[x.id,x]));
function validate(){
 if(EVIDENCE.length!==14||INDEX.size!==14)throw Error("INVALID_EVIDENCE_INDEX");
 for(const e of EVIDENCE){
  if(!/^[A-Za-z0-9_-]{11}$/.test(e.id)||e.anchors.length<2||!e.caption_accessed||e.audio_verified)throw Error("INVALID_CAPTION_PROVENANCE");
  for(const a of e.anchors){
   if(!/^(?:\d{2}:)?\d{2}:\d{2}$/.test(a.timestamp)||!a.topic||a.execution_enabled)throw Error("INVALID_CAPTION_ANCHOR");
  }
 }
 return true;
}
module.exports={EVIDENCE,INDEX,validate};
