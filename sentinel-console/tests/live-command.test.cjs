"use strict";
const test=require("node:test"),assert=require("node:assert/strict");
const fs=require("node:fs"),path=require("node:path"),vm=require("node:vm");
const root=path.resolve(__dirname,"..");
const get=file=>fs.readFileSync(path.join(root,file),"utf8");

test("V3 landing page loads broker-grounded UI and protected live API",()=>{
  const html=get("index.html"),app=get("app.js"),ui=get("live-ui.js"),api=get("api/live.js"),css=get("styles-v3.css");
  assert.match(html,/styles-v3\.css/);
  assert.match(html,/live-ui\.js/);
  assert.match(app,/page:"live",preview:false/);
  assert.match(app,/case"live":h=window\.SentinelLive/);
  assert.match(css,/lc-market-grid/);
  assert.match(api,/SENTINEL_VERCEL_SSO/);
  assert.match(api,/req\.method==="GET"/);
  assert.match(api,/sentinel_cloud_trader_fills/);
  assert.match(api,/SUM\(profit\+swap\+commission\)/);
  assert.match(ui,/READ_ONLY|read-only/i);
  assert.doesNotMatch(ui,/sampleTrades|mockSeries|order_send|placeOrder|api\/gateway|syntheticPrice/);
});

test("read-only command view renders verified loss and escapes broker-supplied strings",async()=>{
  const account={last4:"1964",type:"MT5 DEMO",broker:"Fusion Markets"};
  const response={ok:true,generated_at:"2026-11-19T13:50:00Z",
    trader_at:"2026-11-19T13:47:00Z",account,
    health:{trader:"FRESH",brain:"FRESH",trader_age_seconds:180,
      brain_age_seconds:240,execution_mode:"UNVERIFIED_DEMO_TRIAL",
      trade_status:"COMPLETED",research_status:"COMPLETED"},
    authorization:{enabled:true,expires_at:"2026-11-20T02:16:50Z",risk_pct:.25},
    trades:{intents:1,closed:1,net_by_currency:[{currency:"EUR",net:-43.66}],
      recent:[{symbol:"BTCUSD",family:"trend_pullback",side:"SHORT",
        net:-43.66,currency:"EUR",closed_at:"2026-11-19T03:48:10Z"}],
      orders:[{symbol:"BTCUSD",family:"trend_pullback",side:"SHORT",
        status:"BROKER_POSITION_OR_HISTORY_CONFIRMED",updated_at:"2026-11-19T03:48:10Z"}]},
    brain:{status:"COMPLETED",broker_selection:"FUSION_DEMO",candidates:0,
      analyses:0,cycles_24h:8,trade_cycles_24h:25,
      last_market:{reason:"BROKER_DATA_QUALITY_GATE",missing_spread_ratio:1}},
    markets:[{symbol:"XAUUSD",status:"NO_VALID_CLOSED_BAR_SIGNAL",
      contract_status:"BROKER_CONTRACT_VERIFIED",quote_ready:true,
      quote_age_seconds:40,spread_bps:.13,
      quote:{mid:4088,bid:4087.95,ask:4088.05,at:"2026-11-19T13:49:20Z"},
      history:[{mid:4084},{mid:4085},{mid:4088}]}],
    events:[{at:"2026-11-19T03:48:10Z",type:"BROKER_CLOSED",symbol:"BTCUSD",
      label:"تأكيد صفقة",detail:"SHORT · <script>alert(1)</script>",net:-43.66,currency:"EUR"}]};
  const body=get("live-ui.js");
  const context={
    window:{},
    document:{addEventListener:()=>{},querySelector:()=>null},
    fetch:async()=>({ok:true,json:async()=>response}),
    setTimeout,clearTimeout,setInterval:()=>{},
    AbortController,Intl,Date,Math,Number,String,JSON,Object,Array,Boolean,console,
  };
  vm.runInNewContext(body,context);
  await new Promise(resolve=>setTimeout(resolve,0));
  const html=context.window.SentinelLive.render();
  assert.match(html,/1964/);
  assert.match(html,/BTCUSD/);
  assert.match(html,/43\.66/);
  assert.match(html,/trend_pullback/);
  assert.match(html,/XAUUSD/);
  assert.match(html,/400|4088/);
  assert.doesNotMatch(html,/<script>alert/);
  assert.match(html,/&lt;script&gt;/);
  assert.match(html,/آخر عينات Bid\/Ask الفعلية/);
});

test("broker-verified forward learning remains observational until enough completed demo trades",()=>{
 const brain=get("worker/runner.js"),api=get("api/live.js"),ui=get("live-ui.js");
 assert.match(brain,/forward_broker_feedback/);
 assert.match(brain,/sentinel_cloud_trader_fills/);
 assert.match(brain,/minimum_closed_for_review:30/);
 assert.match(brain,/auto_promotion:false/);
 assert.match(api,/forward_feedback/);
 assert.match(ui,/VERIFIED BROKER FEEDBACK/);
 assert.doesNotMatch(brain,/forward_broker_feedback\s*\.\s*execute/i);
});
test("unauthenticated live API cannot expose broker ledger or accept POST",async()=>{
  const handler=require("../api/live.js");
  const req=method=>({method,headers:{host:"sentinel-mt5-console.vercel.app"}});
  const response=()=>{
    const r={statusCode:0,body:null,headers:{}};
    r.setHeader=(key,value)=>{r.headers[key]=value};
    r.status=n=>{r.statusCode=n;return r};
    r.json=data=>{r.body=data;return r};
    return r;
  };
  const forbidden=response();await handler(req("GET"),forbidden);
  // A deployment-level SSO policy and server config gate the endpoint.
  if(process.env.SENTINEL_VERCEL_SSO!=="enabled")assert.equal(forbidden.statusCode,403);
  const unsafe=response();await handler(req("POST"),unsafe);
  assert.equal(unsafe.statusCode,405);
  assert.equal(unsafe.body.error,"READ_ONLY");
});
