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
 assert.match(js,/page:"overview",preview:false/);
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
