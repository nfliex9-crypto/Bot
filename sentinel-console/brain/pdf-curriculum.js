"use strict";
/**
 * Owner-supplied PDF knowledge index (2026-11-20).
 * Source SHA-256 binds references to the exact uploaded documents. Only short,
 * original paraphrases and page pointers are committed: NO PDF redistribution.
 * Page numbers are 1-indexed physical PDF pages. These are educational claims,
 * not verified statistical edges or evidence of hidden institutional orders.
 */
const SOURCES=Object.freeze([
 {id:"entry_cont_1",name:"11. Entry_Types_Continuation_Part_1.pdf",pages:9,
  sha256:"8ee899dfd5523a5a635bec640f784f7be885ac5a8ad2aa4d8ecf4facb589d828",
  sections:[{page:2,topic:"HTF demand/OB then wait for LTF confirmation"},{page:3,topic:"Single LTF BOS entry"},{page:4,topic:"Double LTF BOS confirmation before continuation"}]},
 {id:"entry_cont_2",name:"12. Entry_Types_Continuations__Liquidity_Part_2.pdf",pages:7,
  sha256:"0e9e99b0b67c5b31ad5e86a39c7798b03a616ab8ddf8eaf8fa0be088ea52c94b",
  sections:[{page:2,topic:"Corrective low break versus momentum break"},{page:3,topic:"Liquidity-seeking break and unmitigated OB"},{page:4,topic:"Continuation entry on LTF after zone revisit"}]},
 {id:"types_liquidity",name:"5. Types_of_Liquidity.pdf",pages:12,
  sha256:"47343ffe5cbeb05543897d2cf0ec4d5ba2ef86be6f026726a65da7845dd3494b",
  sections:[{page:1,topic:"Trendline, range support/resistance, equal highs/lows"},{page:8,topic:"Liquidity sweep and momentum response"},{page:9,topic:"Equal-low sweep then price structure break"}]},
 {id:"price_imbalance",name:"9. Price_Action_Imbalance.pdf",pages:22,
  sha256:"7cbab3843e95f1997df3c003e83d88b49f800cc3d78d70b5a3d49cb5bf9262ff",
  sections:[{page:2,topic:"Three-candle wick gap defines price imbalance"},{page:3,topic:"Price revisits imbalance and order block in example"}]},
 {id:"supply_demand",name:"3. Supply_and_Demand.pdf",pages:18,
  sha256:"1a63b9dda4dae212add35c1e5f131395b2dbe8faf5ef608e9a058233658f877c",
  sections:[{page:2,topic:"Demand zone: consolidation before bullish expansion"},{page:3,topic:"Supply zone: consolidation before bearish expansion"},{page:4,topic:"Return to demand zone after a structure break"}]},
 {id:"liquidity_manip",name:"4. Liquidity_and_Manipulation.pdf",pages:20,
  sha256:"940fc09f78255d031e700b0a07eac4dfd2095b3143e4844883a39582224e657e",
  sections:[{page:2,topic:"EQH/EQL as hypothesized stop clusters"},{page:4,topic:"Stop location is an assumption, not directly observable"}]},
 {id:"ict_mmm",name:"FOREX ICT & MMM NOTES.pdf",pages:109,
  sha256:"7a776c6a1e50aace0c95c9920785938876c07114f15f6187cc924352635ae680",
  sections:[{page:23,topic:"Cross-instrument SMT divergence"},{page:34,topic:"Fair value gap"},{page:43,topic:"Accumulation, false move, then expansion"},{page:44,topic:"Time/price kill zones and DST caution"},{page:45,topic:"Session timing examples to be independently verified"}]},
 {id:"wade_fx",name:"Market_Structure_And_Powerful_Setups_By_Wade_Fx_Setups1_1.pdf",pages:153,
  sha256:"b56f668a6f534f2c14f9a03fa526b64d9c9a8be9fd4e56ee90cdb035dee75331",
  sections:[{page:9,topic:"BMS requires a close beyond a swing level"},{page:80,topic:"Turtle Soup defined as false breakout at liquidity"},{page:81,topic:"Long below lows; short above highs"},{page:88,topic:"Stop hunt -> BMS -> return to OB"},{page:94,topic:"Failure swing -> BMS -> return to OB"}]}
].map(s=>Object.freeze({...s,review_status:"KEY_SECTIONS_REVIEWED",
 raw_document_stored_in_repo:false,statistical_edge_verified:false,
 sections:Object.freeze(s.sections.map(x=>Object.freeze(x)))})));
const SOURCE_MAP=new Map(SOURCES.map(x=>[x.id,x]));
const HYPOTHESES=Object.freeze([
 {id:"turtle_soup_reclaim",label:"Turtle Soup / sweep and reclaim",
  refs:[["wade_fx",80],["wade_fx",81],["types_liquidity",9],["liquidity_manip",4]],
  required:["broker_ohlc"],detector:"sweep_reclaim",
  hypothesis:"Prior local high/low is pierced but price closes back within the prior range"},
 {id:"sh_bms_rto",label:"Stop hunt + structure break + return to order block",
  refs:[["wade_fx",88],["wade_fx",87]],
  required:["broker_ohlc","aligned_multitimeframe"],
  detector:"SEQUENCE_NOT_IMPLEMENTED",
  hypothesis:"Three-stage sequence: sweep, opposite-direction BMS, then retest of defined origin zone"},
 {id:"sms_bms_rto",label:"Failure swing + BMS + RTO",
  refs:[["wade_fx",93],["wade_fx",94]],
  required:["broker_ohlc","aligned_multitimeframe"],
  detector:"SEQUENCE_NOT_IMPLEMENTED",
  hypothesis:"Swing fails to exceed prior extreme, breaks structure, then retests a predeclared zone"},
 {id:"fvg_three_candle",label:"Three-candle FVG / price imbalance",
  refs:[["price_imbalance",2],["price_imbalance",3],["ict_mmm",34]],
  required:["broker_ohlc"],detector:"fvg_three_candle",
  hypothesis:"A non-overlap of first/third candle wicks creates a price-only gap candidate"},
 {id:"htf_zone_double_bos",label:"HTF supply/demand + double LTF BOS",
  refs:[["entry_cont_1",2],["entry_cont_1",4],["entry_cont_2",4],["supply_demand",2]],
  required:["broker_ohlc","aligned_multitimeframe"],
  detector:"SEQUENCE_NOT_IMPLEMENTED",
  hypothesis:"Retest HTF zone and require two LTF structural closes in intended direction"},
 {id:"liquidity_vs_momentum",label:"Corrective break versus displacement",
  refs:[["entry_cont_2",2],["entry_cont_2",3]],
  required:["broker_ohlc"],detector:"displacement_break",
  hypothesis:"Compare candle-body expansion on close beyond local range versus wick-led rejection"},
 {id:"supply_demand_retest",label:"Consolidation/expansion supply and demand",
  refs:[["supply_demand",2],["supply_demand",3],["supply_demand",4]],
  required:["broker_ohlc"],detector:"SEQUENCE_NOT_IMPLEMENTED",
  hypothesis:"Find bounded consolidation before expansion, then wait for price to retest the prior zone"},
 {id:"killzone_amd",label:"Session false move / AMD",
  refs:[["ict_mmm",43],["ict_mmm",44],["ict_mmm",45]],
  required:["broker_ohlc","verified_session_calendar"],
  detector:"SEQUENCE_NOT_IMPLEMENTED",
  hypothesis:"Compare session-range sweep and subsequent expansion with explicit timezone/DST rules"},
 {id:"smt_divergence",label:"SMT cross-market divergence",
  refs:[["ict_mmm",23],["ict_mmm",24]],
  required:["aligned_multisymbol"],detector:"DATA_BLOCKED",
  hypothesis:"Compare swing-extreme confirmation between correlated instruments without inferring causality"}
].map(x=>Object.freeze({...x,refs:Object.freeze(x.refs.map(y=>Object.freeze(y))),
  required:Object.freeze(x.required),execution_enabled:false,
  statistical_edge_verified:false,source_attribution_type:"EDUCATIONAL_RULE_HYPOTHESIS"})));
const DEMO_CAPABILITIES=Object.freeze({broker_ohlc:true,aligned_multitimeframe:false,
 verified_session_calendar:false,aligned_multisymbol:false,broker_historical_bid_ask:false,
 volume_at_price:false,aggressor_side_trades:false,depth_l2:false});
function validate(){
 if(SOURCES.length!==8||SOURCE_MAP.size!==8||HYPOTHESES.length!==9)throw Error("PDF_SOURCE_INDEX_INVALID");
 for(const s of SOURCES){
  if(!/^[a-f0-9]{64}$/.test(s.sha256)||s.pages<1||s.raw_document_stored_in_repo)throw Error("PDF_FINGERPRINT_INVALID");
  for(const sec of s.sections)if(sec.page<1||sec.page>s.pages||!sec.topic)throw Error("PDF_PAGE_INVALID");
 }
 for(const h of HYPOTHESES){
  if(h.execution_enabled||h.statistical_edge_verified||!h.refs.length)throw Error("UNVERIFIED_RULE_AUTHORIZED");
  for(const [id,page] of h.refs)if(!SOURCE_MAP.has(id)||page<1||page>SOURCE_MAP.get(id).pages)
   throw Error("UNKNOWN_RULE_SOURCE_PAGE");
 }
 return true;
}
function status(capabilities=DEMO_CAPABILITIES){
 return {source_kind:"USER_UPLOADED_PDF",source_count:SOURCES.length,
  source_pages:SOURCES.reduce((n,s)=>n+s.pages,0),
  reviewed_section_count:SOURCES.reduce((n,s)=>n+s.sections.length,0),
  proposed_rule_count:HYPOTHESES.length,
  approved_rule_count:0,raw_pdfs_committed:false,
  auto_execution_enabled:false,
  hypotheses:HYPOTHESES.map(h=>{
   const missing=h.required.filter(x=>capabilities[x]!==true);
   return {id:h.id,label:h.label,detector:h.detector,source_refs:h.refs,
    status:missing.length?"DATA_BLOCKED":h.detector==="SEQUENCE_NOT_IMPLEMENTED"?"NOT_IMPLEMENTED":"PRICE_PATTERN_RESEARCH_ONLY",
    missing_inputs:missing,execution_enabled:false,edge_verified:false};
  }),
  sources:SOURCES.map(s=>({id:s.id,name:s.name,pages:s.pages,sha256:s.sha256,
   reviewed_sections:s.sections,review_status:s.review_status}))
 };
}
module.exports={SOURCES,HYPOTHESES,DEMO_CAPABILITIES,validate,status};
