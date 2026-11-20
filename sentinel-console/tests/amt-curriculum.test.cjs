"use strict";
const test=require("node:test"),assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
const a=require("../brain/amt-curriculum.js");
test("all 14 exact video URLs are preserved, none falsely marked processed",()=>{
 assert.equal(a.validateCatalog(),true);
 assert.equal(a.SOURCE_CATALOG.length,14);
 assert.equal(new Set(a.IDS).size,14);
 assert.deepEqual(a.SOURCE_CATALOG.map(x=>x.id),[
 "z4Lq1IGmrS8","dqONJMI1rYM","LwDarLLYg8w","mQ45-sOiQ24",
 "9Ikd_J41kGw","YNersT1IG9s","I-6yE7UtJ5U","M4b8WVfqDtM",
 "ddp6ZIqmaOc","sZhdaMr-fFY","8jtLFS7ZJxo","nLCeDXzJiI8",
 "GeWGu7mBvIc","7HXYhinEkRI"
 ]);
 assert.ok(a.SOURCE_CATALOG.every(s=>s.content_status==="TIMECODED_CAPTIONS_INDEXED_UNAUDITED"&&
  s.captions_indexed&&s.evidence_anchors.length>=2&&
  !s.transcript_verified&&!s.orders_authorized));
});
test("MT5 OHLC cannot masquerade as CVD, footprint, L2 iceberg or true Volume Profile",()=>{
 const r=a.curriculumStatus();
 assert.equal(r.linked_sources,14);
 assert.equal(r.content_read,0);
 assert.equal(r.captions_indexed,14);
 assert.equal(r.caption_evidence_leads,28);
 assert.equal(r.transcripts_verified,0);
 assert.equal(r.autonomous_broker_orders,false);
 assert.equal(r.concept_research.find(x=>x.id==="volume_profile").status,"DATA_UNAVAILABLE");
 assert.equal(r.concept_research.find(x=>x.id==="delta_absorption").status,"DATA_UNAVAILABLE");
 assert.equal(r.concept_research.find(x=>x.id==="iceberg_reload").status,"DATA_UNAVAILABLE");
 assert.equal(r.concept_research.find(x=>x.id==="failed_auction").status,"RESEARCH_DATA_PRESENT_SOURCE_UNVERIFIED");
 assert.ok(r.concept_research.every(x=>x.execution_enabled===false));
});
test("time-coded owner transcript creates only fingerprint, not accepted rules",()=>{
 const r=a.stageTranscript({videoId:a.IDS[0],origin:"OWNER_SUPPLIED",segments:[
  {seconds:12,text:"This is an invented unit-test transcript, not an actual Fabio quote."},
  {seconds:70,text:"We describe a hypothetical range for data provenance."}
 ]});
 assert.match(r.sha256,/^[a-f0-9]{64}$/);
 assert.equal(r.caption_segments,2);
 assert.equal(r.content_status,"TRANSCRIPT_STAGED_UNREVIEWED");
 assert.equal(r.orders_authorized,false);
 assert.equal(r.auto_promotion,false);
 assert.equal(r.fact_extraction_required,true);
 assert.ok(!JSON.stringify(r).includes("hypothetical range"));
});
test("reject unknown source, untrusted captions, missing timestamps and empty transcripts",()=>{
 assert.throws(()=>a.stageTranscript({videoId:"XXXXXXXXXXX",origin:"OWNER_SUPPLIED",segments:[{seconds:0,text:"hi"}]}),/SOURCE_NOT_IN_BOOTCAMP/);
 assert.throws(()=>a.stageTranscript({videoId:a.IDS[0],origin:"WEB_SCRAPE",segments:[{seconds:0,text:"hi"}]}),/TRANSCRIPT_PROVENANCE_REQUIRED/);
 assert.throws(()=>a.stageTranscript({videoId:a.IDS[0],origin:"OWNER_SUPPLIED",segments:[]}),/INVALID_CAPTION_SEGMENTS/);
 assert.throws(()=>a.stageTranscript({videoId:a.IDS[0],origin:"OWNER_SUPPLIED",segments:[{seconds:60,text:"hi"},{seconds:10,text:"earlier"}]}),/INVALID_TIMESTAMPS_OR_TEXT/);
});
test("proposed AMT rules require source provenance; never authorize trading",()=>{
 const s=a.stageTranscript({videoId:a.IDS[0],origin:"OWNER_SUPPLIED",segments:[{seconds:123,text:"Fixture only"}]});
 const r=a.proposedRule({conceptId:"failed_auction",sourceId:a.IDS[0],
  evidenceTimestampSeconds:123,transcriptSha:s.sha256,
  rule:"Require an actual close back inside a previously defined session range."});
 assert.equal(r.approved_for_execution,false);
 assert.equal(r.proven_out_of_sample,false);
 assert.equal(r.forward_evidence,0);
 assert.throws(()=>a.proposedRule({conceptId:"delta_absorption",sourceId:a.IDS[1],
  evidenceTimestampSeconds:0,transcriptSha:"bad",rule:"Use delta divergence as a setup hypothesis."}),/EVIDENCE_REQUIRED/);
});
test("curriculum is separate from independent demo execution order path",()=>{
 const core=fs.readFileSync(path.join(__dirname,"../worker/cloud-trader/core.js"),"utf8");
 const runner=fs.readFileSync(path.join(__dirname,"../worker/cloud-trader/runner.js"),"utf8");
 assert.doesNotMatch(core,/amt-curriculum/);
 assert.doesNotMatch(runner,/amt-curriculum/);
});

test("all 14 videos have caption-derived timecoded leads but no unverified authorizations",()=>{
 const e=require("../brain/amt-evidence.js");
 assert.equal(e.validate(),true);
 assert.equal(e.EVIDENCE.length,14);
 assert.deepEqual(e.EVIDENCE.map(x=>x.id),a.IDS);
 assert.ok(e.EVIDENCE.every(x=>x.caption_accessed&&
   !x.audio_verified&&x.anchors.length>=2&&
   x.anchors.every(p=>!p.video_specific_strategy_validated&&!p.execution_enabled)));
});
