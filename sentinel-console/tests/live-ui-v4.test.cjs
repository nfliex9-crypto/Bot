"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const vm=require("node:vm");
const root=path.resolve(__dirname,"..");
const curriculum=require("../brain/amt-curriculum.js");
const script=fs.readFileSync(path.join(root,"live-ui-v4.js"),"utf8");
const now=Date.now();
const at=offset=>new Date(now+offset).toISOString();
const sample={
 ok:true,generated_at:at(0),trader_at:at(-60000),
 account:{last4:"1964",type:"MT5 DEMO",provider:"TickerAll",broker:"Fusion Markets"},
 health:{trader:"FRESH",brain:"FRESH",trader_age_seconds:60,execution_mode:"UNVERIFIED_DEMO_TRIAL"},
 authorization:{enabled:true,expires_at:at(3600000),risk_pct:.25},
 trades:{intents:1,closed:1,net_by_currency:[{currency:"EUR",net:-43.66}],
  recent:[{symbol:"BTCUSD",family:"trend_pullback",side:"SHORT",net:-43.66,currency:"EUR",closed_at:at(-90000)}],
  orders:[{symbol:"BTCUSD",family:"trend_pullback",side:"SHORT",status:"BROKER_POSITION_OR_HISTORY_CONFIRMED",updated_at:at(-90000)}]},
 brain:{cycles_24h:20,trade_cycles_24h:70,candidates:0,updated_at:at(-120000),
  forward_broker_feedback:{closed:1,minimum_closed_for_review:30,auto_promotion:false,
    strategies:[{symbol:"BTCUSD",family:"trend_pullback",closed:1,booked_net:-43.66,currency:"EUR"}]},
  last_market:{symbol:"BTCUSD",hypotheses:22,missing_spread_ratio:1,reason:"BROKER_DATA_QUALITY_GATE"}},
 markets:[
  {symbol:"XAUUSD",status:"NO_VALID_CLOSED_BAR_SIGNAL",contract_status:"BROKER_CONTRACT_VERIFIED",quote_ready:true,quote_age_seconds:60,
   quote:{bid:4000,ask:4000.2,mid:4000.1},spread_bps:.5,
   history:[{at:at(-3600000),mid:3998},{at:at(-1800000),mid:3999},{at:at(-60000),mid:4000.1}]},
  {symbol:"BTCUSD",contract_status:"BROKER_CONTRACT_VERIFIED",quote_ready:true,quote_age_seconds:60,
   quote:{bid:93000,ask:93025,mid:93012.5},spread_bps:2.7,
   history:[{at:at(-3600000),mid:93100},{at:at(-1800000),mid:93070},{at:at(-60000),mid:93012.5}]}
 ],
 amt_curriculum:{...curriculum.curriculumStatus(),
  sources:curriculum.SOURCE_CATALOG.map(x=>({order:x.order,id:x.id,url:x.url,
    content_status:x.content_status,transcript_verified:false}))},
 pdf_playbook:[{symbol:"BTCUSD",at:at(-60000),closed_bars:780,higher_tf_coverage:.74,
  status:"OHLC_PLUS_RECENT_SPREAD_COST_PROXY_ONLY",execution_enabled:false,families:[
    {family:"sweep_displacement_confirm",status:"RESEARCH_NOT_PROVEN",train_n:7,
     validation_n:3,val_expectancy_r:-.24,val_cost_stress_r:-.51,holdout_n:2},
    {family:"displacement_fvg_retest",status:"RESEARCH_NOT_PROVEN",train_n:6,
     validation_n:3,val_expectancy_r:.11,val_cost_stress_r:-.18,holdout_n:2}
  ]}],
 scan_history:[{at:at(-60000),status:"COMPLETED",orders_sent:0,signals:0,blocked:0}],
 research_history:[{at:at(-120000),status:"COMPLETED",symbol:"BTCUSD",reason:"BROKER_DATA_QUALITY_GATE",hypotheses:22}],
 events:[{at:at(-90000),type:"BROKER_CLOSED",label:"<img src=x onerror=alert(1)>",symbol:"BTCUSD",detail:"SHORT",net:-43.66,currency:"EUR"}]
};
function boot(){
 let handler=null,html="";
 const page={set innerHTML(value){html=value},get innerHTML(){return html}};
 const document={
  addEventListener:(name,cb)=>{if(name==="click")handler=cb},
  querySelector:()=>({}),getElementById:()=>page,visibilityState:"visible"
 };
 const ctx={window:{},document,fetch:async()=>({ok:true,json:async()=>sample}),
  setInterval:()=>0,setTimeout,clearTimeout,AbortController,Intl,Date,Math,Number,String};
 vm.runInNewContext(script,ctx,{filename:"live-ui-v4.js",timeout:2000});
 return {api:ctx.window.SentinelLive,click:handler,page};
}
test("V4 terminal renders only broker-grounded metrics, trade P&L and quote history",async()=>{
 const {api}=boot();
 await new Promise(resolve=>setImmediate(resolve));
 await api.refresh();
 const html=api.render();
 assert.match(html,/SENTINEL \/ TRADING INTELLIGENCE/);
 assert.match(html,/1964/);
 assert.match(html,/43\.66/);
 assert.match(html,/BTCUSD/);
 assert.match(html,/sc-chart-canvas/);
 assert.match(html,/مكتبة تعلّم السوق/);
 assert.match(html,/الروابط الـ14 الأصلية/);
 assert.match(html,/نصوص تم التحقق منها/);
 assert.match(html,/https:\/\/www.youtube.com\/watch\?v=z4Lq1IGmrS8/);
 assert.match(html,/بحاجة بيانات/);
 assert.match(html,/sc-decision-strip/);
 assert.match(html,/بانتظار إشارة/);
 assert.match(html,/FORWARD \/ BROKER-VERIFIED DEMO/);
 assert.match(html,/OWNER PDFS \/ CAUSAL STRATEGY LAB/);
 assert.match(html,/مختبر المعرفة من 8 ملفات/);
 assert.match(html,/sweep_displacement_confirm/);
 assert.match(html,/SHADOW ONLY/);
 assert.match(html,/1 \/ 30/);
 assert.match(html,/<progress class='sc-feedback-track'/);
 assert.doesNotMatch(html,/style='/);
 assert.match(html,/لا يوجد اعتماد تلقائي/);
 assert.match(html,/BROKER_DATA_QUALITY_GATE|نقص تكاليف تاريخية|البحث التاريخي محجوب/);
 assert.match(html,/&lt;img src=x onerror=alert\(1\)&gt;/);
 assert.doesNotMatch(html,/<img src=x onerror=alert\(1\)>/);
 assert.doesNotMatch(script,/sampleTrades|mockSeries|Math\.random/);
});
test("market and time range selectors update actual chart without trade actions",async()=>{
 const {api,click}=boot();
 await new Promise(resolve=>setImmediate(resolve));
 const trigger=(selector,data)=>click({target:{closest:query=>query===selector?{dataset:data}:null}});
 trigger("[data-sc-market]",{scMarket:"BTCUSD"});
 trigger("[data-sc-range]",{scRange:"1"});
 let html=api.render();
 assert.match(html,/بيتكوين <span class='sc-symbol'>BTCUSD/);
 assert.match(html,/data-sc-range='1' class='active'/);
 trigger("[data-sc-ledger]",{scLedger:"orders"});
 html=api.render();
 assert.match(html,/BROKER POSITION OR HISTORY CONFIRMED|BROKER_POSITION_OR_HISTORY_CONFIRMED/);
 assert.doesNotMatch(script,/placeOrder|order_send|executeTrade/);
});
test("V4 API stays read-only and exposes real bounded scan/research histories",()=>{
 const api=fs.readFileSync(path.join(root,"api/live.js"),"utf8");
 const html=fs.readFileSync(path.join(root,"index.html"),"utf8");
 assert.match(api,/req\.method!=="GET"/);
 assert.match(api,/scan_history:scanHistory\.map/);
 assert.match(api,/amt_curriculum:/);
 assert.match(api,/amtCurriculum\.curriculumStatus/);
 assert.match(api,/research_history:researchHistory\.map/);
 assert.match(api,/forward_broker_feedback:research\?\.notes/);
 assert.match(api,/sentinel_pdf_playbook_runs/);
 assert.match(api,/pdf_playbook:\[\.\.\.pdfRecent.values\(\)\]/);
 assert.match(api,/sentinel_autonomy_spread_observations/);
 assert.match(html,/live-ui-v4\.js/);
 assert.match(html,/styles-v4\.css/);
 assert.doesNotMatch(html,/live-ui\.js\?v=sentinel-live-v3/);
});
