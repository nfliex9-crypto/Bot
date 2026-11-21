"use strict";
/**
 * Owner-supplied Orderflows Delta Trading Course, 5 video files / 4 lessons.
 * Provenance: SHA-256 of original uploads, ffprobe durations and sampled
 * on-screen slides. NOT a verified word-for-word audio transcription.
 * Educational paraphrases, not redistributed copyrighted footage.
 * NEVER grants broker execution permission or claims tested edge.
 */
const SOURCES=Object.freeze([
 {id:"delta_l1",file:"Orderflows Delta Trading Course Lesson 1 - Delta Explained(1).mp4",seconds:2198.0,
  sha256:"9cf3555f4c31d96d6fb2c2bc0fec0d50ecb42fdf710a5433846ea7b559c289d1"},
 {id:"delta_l2",file:"Orderflows Delta Trading Course Lesson 2 - How To Read Delta(2).mp4",seconds:945.0,
  sha256:"b840a3a6da231d1f2abaf308142cfcc8a11f107bf3dcb241e25df093c287f763"},
 {id:"delta_l3",file:"Orderflows Delta Trading Course Lesson 3 - Delta Numbers(1).mp4",seconds:1929.0,
  sha256:"bd6dbff480ae32559ce3da2e73c2729be59d9e73a03a90d294713932dbea9ca1"},
 {id:"delta_l4a",file:"Orderflows Delta Trading Course Lesson 4 - Delta Trade Setups(1).mp4",seconds:929.466667,
  sha256:"22369df128c4ac4c8c358c02774ae6c6ca846f23e8e3f5adcf5e188c026415e5"},
 {id:"delta_l4b",file:"Orderflows Delta Trading Course Lesson 4 - Delta Trade Setups.mp4",seconds:852.133333,
  sha256:"2778d1c6fa6aa2cd81a1b7f9f462286ece8c16c9f38fe0ed1a9fd1d145410a21"}
].map(x=>Object.freeze({...x,inspection:"VISUAL_SLIDES_SAMPLED",transcribed_audio:false,stored_in_repo:false})));
const INDEX=Object.freeze([
 {source:"delta_l1",at:"01:00",topic:"One transaction always has a buyer and seller; delta measures the aggressor, not buyer headcount"},
 {source:"delta_l1",at:"04:00",topic:"Passive buyers/sellers supply liquidity; aggressive buys lift offers and aggressive sells hit bids"},
 {source:"delta_l1",at:"07:28",topic:"Delta is executed aggressive-buy size minus executed aggressive-sell size"},
 {source:"delta_l1",at:"11:00",topic:"Positive delta does not mechanically cause bullish price movement"},
 {source:"delta_l1",at:"17:00",topic:"Price/delta disagreement may reflect passive absorption; iceberg is not proven by delta alone"},
 {source:"delta_l1",at:"22:00",topic:"Intrabar changes in who is aggressive and attempts to control price"},
 {source:"delta_l1",at:"31:00",topic:"Illustrated accumulation/distribution scenarios; interpretations require price context"},
 {source:"delta_l2",at:"01:00",topic:"Single delta bar versus a sequence of bars"},
 {source:"delta_l2",at:"02:00",topic:"Delta chart displaying final delta values"},
 {source:"delta_l2",at:"05:00",topic:"Delta candle, separate delta-based visual representation"},
 {source:"delta_l2",at:"09:00",topic:"Delta footprint, volume imbalance at each price level"},
 {source:"delta_l2",at:"12:00",topic:"Diagonal delta footprint, compares adjacent price levels"},
 {source:"delta_l2",at:"14:00",topic:"No single display style required; choose to fit interpretation"},
 {source:"delta_l3",at:"01:00",topic:"Final, maximum, minimum and cumulative delta; cumulative delta divided by volume"},
 {source:"delta_l3",at:"02:00",topic:"Bar construction (time versus range) affects delta interpretation"},
 {source:"delta_l3",at:"03:00",topic:"Final delta is fixed after close but changes during the bar"},
 {source:"delta_l3",at:"06:00",topic:"Market open/close volume regime affects raw magnitude"},
 {source:"delta_l3",at:"10:00",topic:"Max delta is the intrabar running-delta maximum, not the largest historical bar close"},
 {source:"delta_l3",at:"15:00",topic:"Min delta is the intrabar running-delta minimum"},
 {source:"delta_l3",at:"21:00",topic:"Alternating max/min can reveal shifts in dominance"},
 {source:"delta_l3",at:"23:00",topic:"Running cumulative delta can lag when older observations dominate"},
 {source:"delta_l3",at:"26:00",topic:"Session cumulative delta divided by session executed volume"},
 {source:"delta_l3",at:"29:00",topic:"Cumulative delta/volume can flatten as denominator grows; lower priority for instructor"},
 {source:"delta_l4a",at:"06:30",topic:"Delta surge grows in positive or negative direction across bars; turning points/consolidation context"},
 {source:"delta_l4a",at:"09:00",topic:"Four-bar long: negative, positive, stronger positive, still stronger positive"},
 {source:"delta_l4a",at:"10:00",topic:"Long delta surge worked examples in footprint charts"},
 {source:"delta_l4a",at:"12:00",topic:"Delta surge short counterpart and examples"},
 {source:"delta_l4b",at:"00:00",topic:"Instructor prefers surge appearing out of sideways activity; market-state context matters"},
 {source:"delta_l4b",at:"01:30",topic:"Short divergence: equal/new price high with negative delta; long divergence: equal/new low with positive delta"},
 {source:"delta_l4b",at:"04:00",topic:"Divergence also applies to intermediate swings, not only day extremes"},
 {source:"delta_l4b",at:"05:30",topic:"Flip: sharp change from selling to buying (or inverse) over two bars"},
 {source:"delta_l4b",at:"06:30",topic:"Long flip 0 max -> near min, then 0 min -> near max; short opposite"},
 {source:"delta_l4b",at:"08:00",topic:"Visual flip examples with footprint charts"},
 {source:"delta_l4b",at:"12:30",topic:"Instructor allows an intervening single bar in some flip examples"}
].map(x=>Object.freeze({...x,evidence:"SLIDE_OR_SAMPLED_FRAME",audio_verified:false})));
const SETUPS=Object.freeze([
 {id:"delta_surge",name:"Delta Surge",source:"delta_l4a",at:"09:00",status:"RULE_FROM_VISIBLE_SLIDE",
  expressions:{long:"d1<0 && d2>0 && d3>d2 && d4>d3",
               short:"d1>0 && d2<0 && d3<d2 && d4<d3"},
  context:"Instructor favors a shift from sideways price action; context is not quantified.",
  unspecified:["entry timing","stop loss","take profit","volume threshold","session"]},
 {id:"delta_divergence",name:"Delta Divergence",source:"delta_l4b",at:"01:30",status:"RULE_FROM_VISIBLE_SLIDE",
  expressions:{long:"current price makes new/equal low and current final delta > 0",
               short:"current price makes new/equal high and current final delta < 0"},
  context:"Use intermediate swing highs/lows or day highs/lows.",
  unspecified:["pivot detection","equal-price tolerance","entry timing","stop loss","take profit"]},
 {id:"delta_flips",name:"Delta Flips",source:"delta_l4b",at:"06:30",status:"RULE_FROM_VISIBLE_SLIDE",
  expressions:{long:"A max delta=0 and closes near min; B min delta=0 and closes near max",
               short:"A min delta=0 and closes near max; B max delta=0 and closes near min"},
  context:"Sometimes one bar between A and B (12:30).",
  unspecified:["numerical meaning of near","entry timing","stop loss","take profit"]},
 {id:"delta_transition",name:"Delta Transition",status:"NAMED_NOT_EXPLAINED"},
 {id:"delta_tails",name:"Delta Tails",status:"NAMED_NOT_EXPLAINED"},
 {id:"delta_bulges",name:"Delta Bulges",status:"NAMED_NOT_EXPLAINED"},
 {id:"delta_reversal",name:"Delta Reversal",status:"NAMED_NOT_EXPLAINED"}
].map(x=>Object.freeze({...x,execution_enabled:false,edge_verified:false})));
const REQUIRED_FEED=Object.freeze({
 timestamp_utc:"executed trade time from the matching venue",
 executed_size:"actual executed trade size (not MT5 tick volume)",
 aggressor_side:"aggressive BUY/SELL from tape or explicitly estimated",
 sequence_id:"strict order for intrabar max/min reconstruction",
 price:"executed trade price and tick size",
 session_id:"verified exchange/session reset boundary"
});
function validate(){
 if(SOURCES.length!==5||SETUPS.length!==7||INDEX.length<30)throw Error("DELTA_VIDEO_CORPUS_INCOMPLETE");
 const seen=new Set();
 for(const s of SOURCES){
  if(seen.has(s.id)||s.seconds<=0||!/^[a-f0-9]{64}$/.test(s.sha256)||s.transcribed_audio||s.stored_in_repo)throw Error("VIDEO_PROVENANCE_INVALID");
  seen.add(s.id);
 }
 for(const a of INDEX)if(!seen.has(a.source)||!/^(\d\d):(\d\d)$/.test(a.at)||a.audio_verified)throw Error("INVALID_VIDEO_EVIDENCE");
 for(const x of SETUPS)if(x.execution_enabled||x.edge_verified)throw Error("UNVERIFIED_DELTA_RULE_ARMED");
 return true;
}
function status(feed={}){
 return {source:"OWNER_UPLOADED_ORDERFLOWS_COURSE",files:5,lessons:4,
  total_seconds:SOURCES.reduce((s,x)=>s+x.seconds,0),
  visual_evidence_anchors:INDEX.length,
  video_audio_transcribed:false,complete_spoken_coverage:false,
  visual_rules_extracted:3,only_names_not_rules:4,
  supported:setupsForStatus(),required_data:REQUIRED_FEED,
  data_ready:feed.executed_tape===true&&feed.aggressor_side===true&&feed.sequence_id===true,
  execution_enabled:false,auto_promotion:false};
}
function setupsForStatus(){return SETUPS.map(s=>({id:s.id,status:s.status,source:s.source||null,at:s.at||null,execution_enabled:false}));}
module.exports={SOURCES,INDEX,SETUPS,REQUIRED_FEED,validate,status};
