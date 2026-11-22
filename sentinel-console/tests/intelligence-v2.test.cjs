"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const v=require("../brain/intelligence-v2.js");
const now=Date.UTC(2026,10,22,14,0);
function data(){
 function make(n,ms,step,origin){
  return Array.from({length:n},(_,i)=>{
   const time=now-(n-i)*ms,open=origin+i*step,close=open+step*.75;
   return {time,open,close,high:close+step*.3,low:open-step*.25};
  });
 }
 return {m15:make(140,900000,.09,100),h1:make(100,3600000,.18,95)};
}
function sourceSignal(m15){
 const last=m15.at(-1);return {family:"pdf_sweep_bos",symbol:"XAUUSD",side:1,
  bar_time:last.time,source_kind:"OWNER_PDF_PRICE_PATTERN",
  source_pdf:"Market_Structure_And_Powerful_Setups_By_Wade_Fx_Setups1_1.pdf",
  source_pages:[80,81]};
}
test("V2 reads closed M15/H1 and explains regime and score without orders",()=>{
 const d=data(),signal=sourceSignal(d.m15);
 const x=v.rank({...d,signals:[signal],now,venue:"FUSION_MT5"});
 assert.equal(x.ready,true,JSON.stringify(x));
 assert.equal(x.ranked.length,1);
 assert.equal(x.ranked[0].source,"OWNER_PDF_PRICE_PATTERN");
 assert.equal(x.ranked[0].orderExecutionAllowed,false);
 assert.equal(x.executionEnabled,false);
 assert.equal(x.ranked[0].orderflow.status,"NOT_PROVIDED");
 assert.equal(x.scoreBasis,"GROSS_PRICE_ONLY_NO_TRANSACTION_COSTS");
 assert.ok(x.ranked[0].score>=0&&x.ranked[0].score<=1);
 assert.equal(x.ranked[0].scoreMeaning,"HEURISTIC_SETUP_QUALITY_NOT_WIN_PROBABILITY");
});
test("causal engine rejects future, missing and corrupted price bars",()=>{
 const d=data(),s=sourceSignal(d.m15);
 const future=[...d.m15,{...d.m15.at(-1),time:now,close:500,high:501}];
 assert.equal(v.rank({...d,m15:future,signals:[s],now}).ready,false);
 const gap=d.m15.slice();gap[gap.length-2]={...gap.at(-2),time:gap.at(-2).time+60000};
 assert.equal(v.rank({...d,m15:gap,signals:[s],now}).ready,false);
 const bad=d.m15.map((x,i)=>i===20?{...x,low:x.high+2}:x);
 assert.equal(v.rank({...d,m15:bad,signals:[s],now}).ready,false);
});
test("unattributed or invented instructor rules never enter ranked set",()=>{
 const d=data(),signal=sourceSignal(d.m15);
 const forged={...signal,source_pages:[]};
 const unknown={...signal,family:"unverified_video_setup"};
 const x=v.rank({...d,signals:[forged,unknown],now});
 assert.equal(x.ranked.length,0);
 assert.ok(x.candidates.every(y=>y.status==="BLOCKED_SOURCE"));
});
test("separate Binance BTCUSDT Delta cannot be used as Fusion XAUUSD evidence",()=>{
 const d=data(),signal=sourceSignal(d.m15);
 const t=signal.bar_time,raw={closed:true,sourceQuality:"VERIFIED_AGGRESSOR_TRADES",
  venue:"BINANCE_SPOT",symbol:"BTCUSDT",openTime:t,closeTime:t+900000,delta:123,volume:600};
 const out=v.rank({...d,signals:[signal],orderflow:raw,venue:"FUSION_MT5",now});
 assert.equal(out.ranked[0].orderflow.status,"REJECTED_MISMATCHED_OR_SYNTHETIC");
 assert.equal(out.ranked[0].orderflow.weight,0);
});
test("verified executed-trade tape is accepted only for exactly matching venue, symbol and closed bar",()=>{
 const t=now-900000;
 const a={closed:true,sourceQuality:"VERIFIED_AGGRESSOR_TRADES",venue:"BINANCE_SPOT",
  symbol:"BTCUSDT",openTime:t,closeTime:now,volume:20,delta:6};
 assert.equal(v.verifiedTape(a,{symbol:"BTCUSDT",venue:"BINANCE_SPOT",barTime:t,closeTime:now}).status,"VERIFIED_EXECUTED_TRADE_TAPE");
 assert.equal(v.verifiedTape({...a,sourceQuality:"OHLC_TICK_VOLUME"},{symbol:"BTCUSDT",venue:"BINANCE_SPOT",barTime:t,closeTime:now}).weight,0);
 assert.equal(v.verifiedTape({...a,closed:false},{symbol:"BTCUSDT",venue:"BINANCE_SPOT",barTime:t,closeTime:now}).weight,0);
 assert.equal(v.verifiedTape(a,{symbol:"BTCUSD",venue:"BINANCE_SPOT",barTime:t,closeTime:now}).weight,0);
});
test("strategy hypotheses never silently become source-verified instructor rules",()=>{
 const d=data(),s={...sourceSignal(d.m15),family:"trend_delta_surge",
  source_kind:undefined,kind:"COMPOSITE_RESEARCH_HYPOTHESIS"};
 const x=v.rank({...d,signals:[s],now});
 assert.equal(x.ranked.length,1);
 assert.equal(x.ranked[0].source,"COMPOSITE_RESEARCH_HYPOTHESIS");
 assert.equal(x.ranked[0].action,"ANALYZE_ONLY");
 assert.equal(v.rank({...d,signals:[{...s,kind:"COURSE_VERIFIED"}],now}).ranked.length,0);
});
function fill(i,{profit=20,tag=true,duplicate=false}={}){
 const open=Date.UTC(2026,8,1)+i*86400000;
 return {accountId:"fusion-demo",ticket:duplicate?"DUPLICATE":String(1000+i),
  symbol:"XAUUSD",family:"pdf_sweep_bos",isDemo:true,brokerVerified:true,
  complete:true,partial:false,openTime:new Date(open).toISOString(),
  closeTime:new Date(open+3600000).toISOString(),
  taggedAt:new Date(open+(tag? -3600000:7200000)).toISOString(),
  grossProfit:profit,riskAtEntry:10};
}
test("forward learner uses genuine, pretagged, closed demo trades and chronological OOS",()=>{
 const trades=Array.from({length:80},(_,i)=>fill(i,{profit:i<52?20:i%4===0?-10:20}));
 const a=v.forwardEvidence(trades);
 assert.equal(a.accepted,80);
 assert.equal(a.strategies.length,1);
 const s=a.strategies[0];
 assert.equal(s.train.trades,52);assert.equal(s.oos.trades,28);
 assert.equal(s.status,"PROMISING_REQUIRES_INDEPENDENT_REVIEW");
 assert.equal(s.promotedToDemo,false);assert.equal(s.executionApproved,false);
 assert.equal(a.costDeductions,0);assert.equal(a.ordersEnabled,false);
});
test("insufficient samples, future tags, duplicates and fake fill provenance do not promote",()=>{
 const data=[fill(0),fill(1,{tag:false}),fill(2),fill(3,{duplicate:true}),
  fill(4,{duplicate:true}),{...fill(5),brokerVerified:false},{...fill(6),isDemo:false}];
 const x=v.forwardEvidence(data);
 assert.equal(x.accepted,3);assert.equal(x.rejected,4);
 assert.equal(x.strategies[0].status,"COLLECTING_FORWARD");
 assert.equal(x.strategies[0].executionApproved,false);
});
test("identical fixed input gives deterministic ranking independent of later tape",()=>{
 const d=data(),sig=sourceSignal(d.m15);
 const baseline=v.rank({...d,signals:[sig],now});
 const next=v.rank({...d,signals:[sig],now});
 assert.deepEqual(baseline,next);
 assert.equal(v.rank({...d,signals:[{...sig,bar_time:sig.bar_time-900000}],now}).ranked.length,0);
});

test("source name must match the verified original PDF",()=>{
 const d=data(),signal=sourceSignal(d.m15);
 const other={...signal,source_pdf:"invented_course_lesson.pdf"};
 assert.equal(v.rank({...d,signals:[other],now}).ranked.length,0);
 assert.equal(v.rank({...d,signals:[signal],now}).ranked.length,1);
});
test("forward learner refuses future trades and unbounded invalid gross-R outcomes",()=>{
 const future=fill(130);
 const infinite={...fill(9),ticket:"INF",grossProfit:Number.MAX_VALUE,riskAtEntry:Number.MIN_VALUE};
 const good=fill(8);
 const r=v.forwardEvidence([future,infinite,good],{asOf:Date.UTC(2026,10,22)});
 assert.equal(r.accepted,1);
 assert.equal(r.rejected,2);
 assert.equal(r.ordersEnabled,false);
});
test("V2 module cannot submit orders or import broker credentials",()=>{
 const fs=require("node:fs"),path=require("node:path");
 const source=fs.readFileSync(path.join(__dirname,"../brain/intelligence-v2.js"),"utf8");
 assert.doesNotMatch(source,/\.submit\s*\(|\/orders\b|process\.env|fetch\s*\(/);
 assert.match(source,/executionEnabled:false/);
});

test("research and future demo use identical canonical market-regime labels",()=>{
 const d=data(),canonical=require("../worker/cloud-trader/regime-intelligence.js").analyze(d.m15,d.h1);
 const research=v.marketFeatures({...d,now});
 assert.equal(canonical.ok,true);
 assert.equal(research.ready,true);
 assert.equal(research.regime,canonical.regime);
 assert.ok(["TRENDING","RANGING","TRANSITION","VOLATILE"].includes(research.regime));
});
