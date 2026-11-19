"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const root=path.resolve(__dirname,"..");
const file=name=>fs.readFileSync(path.join(root,name),"utf8");
test("production HTML uses the new MT5 onboarding and responsive theme",()=>{
 const html=file("index.html");
 assert.match(html,/styles-v2\.css/);
 assert.match(html,/free-ui\.js/);
 assert.match(html,/ربط MT5/);
 assert.doesNotMatch(html,/الاتصال بالبوت|Sentinel Console Access Key/);
});
test("no broken login-to-unconfigured-bot flow triggers on load",()=>{
 const js=file("app.js"),mt=file("free-ui.js");
 assert.match(js,/page:"live",preview:false/);
 assert.doesNotMatch(js,/if\(state\.key\)\{connect\(\)\}/);
 assert.match(js,/window\.FreeMT5UI\?\.sync/);
 assert.match(mt,/window\.FreeMT5UI\.init\(\)/);
 assert.doesNotMatch(mt,/x-console-key|consoleKey|sentinel_console_key/);
});
test("there is no invented account equity or trading demo P&L on overview",()=>{
 const js=file("app.js");
 const start=js.indexOf("function overview(){"),end=js.indexOf("function tradesView(){",start);
 const overview=js.slice(start,end);
 assert.ok(overview.length>100);
 assert.doesNotMatch(overview,/sampleTrades|mockSeries|5511\.2|SAMPLE/);
 assert.match(overview,/mt\.verified/);
});
test("provider operations require deployment-level SSO and demo checks",()=>{
 const source=file("api/free-mt5.js");
 assert.match(source,/SENTINEL_VERCEL_SSO/);
 assert.match(source,/protectedRequest\(req\)/);
 assert.match(source,/a\.isDemo===true/);
 assert.doesNotMatch(source,/req\.headers\["x-console-key"\]/);
});

test("MT5 demo ONLINE is independent of broker equity, no redundant verification step",()=>{
 const ui=file("free-ui.js");
 assert.doesNotMatch(ui,/section\("Verified",3/);
 assert.match(ui,/a\.online/);
 assert.match(ui,/financialsReady/);
 const backend=file("api/free-mt5.js");
 assert.match(backend,/base\.online=/);
 assert.match(backend,/base\.verificationError=/);
});

test("broker ONLINE can precede balance snapshot without generating fake zero",()=>{
 const ui=file("free-ui.js");
 const overview=file("app.js");
 assert.match(ui,/financialsReady/);
 assert.match(overview,/mt\.financialsReady&&mt\.balance!=null/);
 assert.match(overview,/mt\.financialsReady&&mt\.equity!=null/);
 assert.doesNotMatch(ui,/section\("Verified",3/);
});

test("AI page triggers bounded broker-history catch-up without always-on execution",()=>{
 const ui=file("brain-ui.js"),app=file("app.js");
 assert.match(ui,/async function maybeAutoSync/);
 assert.match(ui,/lastAutoAttempt/);
 assert.match(ui,/6\*3600\*1000/);
 assert.match(ui,/call\("syncTrades"/);
 assert.match(ui,/call\("syncCandles"/);
 assert.match(ui,/call\("evaluate"/);
 assert.match(app,/SentinelBrain\?\.maybeAutoSync/);
 assert.doesNotMatch(ui,/placeOrder|order_send|place_order/);
});
test("forward learning is scoped by symbol and market-regime evidence is visible",()=>{
 const ui=file("brain-ui.js");
 assert.match(ui,/forward_by_account_symbol/);
 assert.match(ui,/Market Regime Lab/);
 assert.match(ui,/active_days/);
 assert.match(ui,/recent_mean_r/);
});

test("research UI distinguishes incomplete source data from verified performance",()=>{
 const ui=file("brain-ui.js");
 assert.match(ui,/Data Quality/);
 assert.match(ui,/missing_spread_ratio/);
 assert.match(ui,/source_coverage/);
 assert.match(ui,/time_gap_events/);
});

test("quant evidence export is flat Perspective-compatible data and never a trading action",()=>{
 const ui=file("brain-ui.js");
 assert.match(ui,/const exportRows=/);
 assert.match(ui,/dataset_sha256:/);
 assert.match(ui,/adjusted_lower_bound_r:/);
 assert.match(ui,/fileDownload\(filename,JSON\.stringify\(exportRows,null,2\)/);
 assert.match(ui,/execution_enabled:false/);
});
