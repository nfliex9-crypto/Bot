"use strict";
const test=require("node:test"),assert=require("node:assert/strict");
const fs=require("node:fs"),path=require("node:path");
const pdf=require("../brain/pdf-curriculum.js");
const lab=require("../brain/source-patterns.js");
const TF=900000,BASE=Date.UTC(2026,10,1);
function fixture(n=60){
 return Array.from({length:n},(_,i)=>({
  timestamp:BASE+i*TF,open:100,high:100.3,low:99.7,close:100.05
 }));
}
test("all eight user-supplied PDFs are fingerprinted, page-cited, never copied to repo",()=>{
 assert.equal(pdf.validate(),true);
 const status=pdf.status();
 assert.equal(status.source_count,8);
 assert.equal(status.source_pages,350);
 assert.equal(status.proposed_rule_count,9);
 assert.equal(status.approved_rule_count,0);
 assert.equal(status.raw_pdfs_committed,false);
 assert.equal(status.auto_execution_enabled,false);
 assert.ok(pdf.SOURCES.every(s=>/^[a-f0-9]{64}$/.test(s.sha256)&&s.sections.length>=2));
 assert.ok(status.hypotheses.every(x=>!x.execution_enabled&&!x.edge_verified));
 assert.ok(status.hypotheses.find(x=>x.id==="smt_divergence").missing_inputs.includes("aligned_multisymbol"));
 assert.ok(status.hypotheses.find(x=>x.id==="sh_bms_rto").missing_inputs.includes("aligned_multitimeframe"));
});
test("Turtle Soup long requires prior-low sweep AND close back inside range",()=>{
 const data=fixture();
 data[25]={...data[25],low:99.2,close:100.1};
 const signals=lab.at(data,25);
 const x=signals.find(x=>x.family==="sweep_reclaim");
 assert.equal(x.side,"LONG");
 assert.equal(x.level,99.7);
 assert.equal(x.orderflow_verified,false);
 assert.equal(x.execution_enabled,false);
 assert.deepEqual(x.source_pages[0],["wade_fx",80]);
 data[25]={...data[25],close:99.4};
 assert.equal(lab.at(data,25).some(x=>x.family==="sweep_reclaim"),false);
});
test("Turtle Soup short requires prior-high sweep AND close back inside range",()=>{
 const data=fixture();
 data[25]={...data[25],high:100.9,close:100};
 const x=lab.at(data,25).find(x=>x.family==="sweep_reclaim");
 assert.equal(x.side,"SHORT");
 assert.equal(x.level,100.3);
});
test("three-candle FVG is a wick gap, not a claim of guaranteed price refill",()=>{
 const data=fixture();
 data[24]={...data[24],open:100,high:100.3,low:99.7,close:100.05};
 data[25]={...data[25],open:100,high:101.4,low:99.9,close:101.3};
 data[26]={...data[26],open:101.2,high:101.6,low:100.7,close:101.4};
 const x=lab.at(data,26).find(x=>x.family==="fvg_three_candle");
 assert.equal(x.side,"LONG");
 assert.ok(x.gap>.3);
 assert.equal(x.data_type,"BROKER_OHLC_PRICE_ONLY");
 assert.equal(x.broker_cost_verified,false);
 assert.equal(x.edge_verified,false);
 data[26]={...data[26],low:100.2};
 assert.equal(lab.at(data,26).some(x=>x.family==="fvg_three_candle"),false);
});
test("displacement break requires strong body close beyond prior range",()=>{
 const data=fixture();
 data[25]={...data[25],open:100,high:102.1,low:99.9,close:102};
 const x=lab.at(data,25).find(x=>x.family==="displacement_break");
 assert.equal(x.side,"LONG");
 data[25]={...data[25],open:100,high:102.1,low:99.9,close:100.1};
 assert.equal(lab.at(data,25).some(x=>x.family==="displacement_break"),false);
});
test("closed-bar scanner excludes open candles, only reports descriptive outcomes",()=>{
 const data=fixture(70),now=data.at(-1).timestamp+TF/2;
 data[60]={...data[60],low:99.2,close:100.1};
 const r=lab.scanRecent(data,{now,tfMs:TF});
 assert.equal(r.status,"PRICE_PATTERN_OBSERVATIONS_ONLY");
 assert.equal(r.excluded_open_bars,1);
 assert.equal(r.closed_bars,69);
 assert.equal(r.execution_enabled,false);
 assert.equal(r.auto_promotion,false);
 assert.ok(r.counts.sweep_reclaim>=1);
 assert.ok(r.descriptive_forward_only.sweep_reclaim.labeled>=1);
 assert.ok(r.warnings.includes("NOT_OUT_OF_SAMPLE_OR_PROFITABILITY_EVIDENCE"));
 assert.ok(r.events.every(x=>!x.execution_enabled));
});
test("future bars never alter past signals; malformed or duplicate bars rejected",()=>{
 const data=fixture(60);
 data[24]={...data[24],low:99.2,close:100.1};
 const prior=lab.at(data,24);
 const changed=data.map((b,i)=>i>24?{...b,open:150,high:170,low:140,close:160}:b);
 assert.deepEqual(lab.at(changed,24),prior);
 assert.throws(()=>lab.normalize([data[0],data[0]]),/INVALID_SOURCE_BAR/);
 assert.throws(()=>lab.normalize([{...data[0],low:200}]),/INVALID_SOURCE_BAR/);
});
test("PDF knowledge is isolated from broker execution module",()=>{
 const core=fs.readFileSync(path.join(__dirname,"../worker/cloud-trader/core.js"),"utf8");
 const runner=fs.readFileSync(path.join(__dirname,"../worker/cloud-trader/runner.js"),"utf8");
 assert.doesNotMatch(core,/pdf-curriculum|source-patterns/);
 assert.doesNotMatch(runner,/pdf-curriculum|source-patterns/);
});
