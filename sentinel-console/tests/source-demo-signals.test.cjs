"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const c=require("../worker/cloud-trader/core.js");
const pdf=require("../worker/cloud-trader/source-signals.js");
const MS=900000,HH=3600000;
const now=Date.UTC(2026,10,20,12);
function series(n,tf,start,step){
 return Array.from({length:n},(_,i)=>{
  const close=start+i*step;
  return {time:now-(n-i)*tf,open:close-step*.3,
   high:close+.10,low:close-.10,close};
 });
}
function bullishSweep(){
 const m=series(140,MS,1900,.06),h=series(120,HH,1900,.25);
 const i=m.length-1;
 const priorLow=Math.min(...m.slice(i-17,i-1).map(x=>x.low));
 m[i-1]={...m[i-1],open:priorLow+.25,close:priorLow+.30,
  low:priorLow-.4,high:priorLow+.43};
 m[i]={...m[i],open:m[i-1].high-.1,
  close:m[i-1].high+.18,low:m[i-1].high-.17,high:m[i-1].high+.28};
 return {m,h};
}
function bullishFVG(){
 const m=series(140,MS,1900,.05),h=series(120,HH,1900,.25);
 const i=m.length-1,j=i-6,a=m[j-2],base=a.high;
 m[j-1]={...m[j-1],open:a.close,close:base+.20,
  low:a.close-.04,high:base+.25};
 m[j]={...m[j],open:base+.27,low:base+.25,
  close:base+.42,high:base+.47};
 for(let k=j+1;k<i;k++){
  const close=base+.49+(k-j)*.035;
  m[k]={...m[k],open:close-.06,close,low:close-.10,high:close+.08};
 }
 m[i]={...m[i],open:base+.40,low:base+.24,
  close:base+.53,high:base+.58};
 return {m,h};
}
test("PDF sweep -> closed BOS with H1 trend enters research-only DEMO source path",()=>{
 const {m,h}=bullishSweep(),s=c.decide("XAUUSD",m,h,now,"source_only");
 assert.ok(s,JSON.stringify(s));assert.equal(s.family,"pdf_sweep_bos");
 assert.equal(s.side,1);assert.equal(s.edge_verified,false);
 assert.ok(s.source_pages.includes(88));assert.ok(pdf.RULES[s.family]);
 assert.equal(c.keyFor("acc_demo",s),c.keyFor("acc_demo",s));
 assert.equal(c.preflight({signal:s,quote:{bid:s.reference_close-.05,
  ask:s.reference_close+.05},spec:{specSource:"broker",point:.01,tickSize:.01,
  tickValueAccount:1,tickValueCurrency:{source:"wire",code:"EUR"},
  digits:2,volumeMin:.01,volumeStep:.01,volumeMax:100,stopLevel:0},
  accountCurrency:"EUR",equity:5000,now}).ok,true);
});
test("PDF FVG: only first retest of closed three-bar wick gap qualifies",()=>{
 const {m,h}=bullishFVG(),s=c.decide("XAUUSD",m,h,now,"source_only");
 assert.ok(s);assert.equal(s.family,"pdf_fvg_retest");
 assert.deepEqual(s.source_pages,[2,3]);
 const touched=m.map(x=>({...x}));
 touched[touched.length-4].low=m[m.length-7].low;
 assert.equal(c.decide("XAUUSD",touched,h,now,"source_only"),null);
});
test("No future bars, stale market or opposing H1 bias can generate PDF order",()=>{
 const {m,h}=bullishSweep();
 assert.equal(c.decide("XAUUSD",m,h,now+9*HH,"source_only"),null);
 assert.equal(c.decide("XAUUSD",[...m,{...m.at(-1),time:now,
   high:m.at(-1).high+.2}],h,now,"source_only"),null);
 const down=series(120,HH,1950,-.25);
 assert.equal(c.decide("XAUUSD",m,down,now,"source_only"),null);
});
test("Unrecognized source execution modes are never silently enabled",()=>{
 const {m,h}=bullishSweep();
 assert.throws(()=>c.decide("XAUUSD",m,h,now,"auto_live"),/INVALID_STRATEGY_MODE/);
 assert.equal(c.demoExecutionAllowed({}, {id:"demo",broker:"mt5",isDemo:true,hot:true}),false);
});
