"use strict";
const {test}=require("node:test");const assert=require("node:assert/strict");
const c=require("../worker/cloud-trader/core.js");
const {provider}=require("../worker/cloud-trader/provider.js");
const {runCloudCycle,pickSymbols}=require("../worker/cloud-trader/runner.js");
function bars(n,period,now,price=1.05,growth=.00025){const start=now-n*period;return Array.from({length:n},(_,i)=>{
  const close=price+i*growth;return {timestamp:(start+i*period)/1000,open:close-growth/2,high:close+growth/2,low:close-growth/2,close};
})}
function signalFixture(now){const m=c.parseCandles(bars(150,900000,now),"M15",now);const h=c.parseCandles(bars(100,3600000,now),"H1",now);
  // Previous bar dips under fast EMA, current fully closed recovers with trend.
  m.at(-2).close-=.0025;m.at(-2).low=m.at(-2).close-.0001;
  m.at(-1).close+=.001;m.at(-1).high=m.at(-1).close+.0001;
  return {m,h};
}
test("closed-bar rules produce deterministic directional signal, not current open bar",()=>{
 const now=Date.UTC(2026,10,18,20,0),{m,h}=signalFixture(now);
 const s=c.decide("EURUSD",m,h,now);assert.ok(s);assert.equal(s.side,1);assert.ok(["trend_pullback","donchian_breakout"].includes(s.family));
 assert.equal(c.parseCandles([...bars(120,900000,now),{...bars(1,900000,now+900000)[0]}],"M15",now).length,120);
 assert.equal(c.decide("EURUSD",m,h,now+9*3600000),null);
});
test("rejects malformed, future, duplicated or unsorted broker OHLC",()=>{
 const b=bars(3,900000,Date.now());assert.throws(()=>c.parseCandles([b[1],b[0]],"M15"),/INVALID/);
 assert.throws(()=>c.parseCandles([b[1],b[1]],"M15"),/INVALID/);
 assert.throws(()=>c.parseCandles([{...b[0],low:9}],"M15"),/INVALID/);
});
test("connected account selection cannot silently cross from MT5 demo to real",()=>{
 const x=[{id:"acc_live",broker:"mt5",isDemo:false,hot:true},{id:"acc_demo",broker:"mt5",isDemo:true,hot:true}];
 assert.equal(c.selectAccount(x,null).account.id,"acc_demo");
 assert.equal(c.selectAccount(x,"acc_live").account,null);
 assert.equal(c.selectAccount([...x,{...x[1],id:"acc_other"}],null).status,"MULTIPLE_DEMOS_AMBIGUOUS");
 assert.equal(c.selectAccount([...x,{...x[1],id:"acc_other"}],null,"acc_other").account.id,"acc_other");
});
test("lot sizes and stop risk use broker account-currency tick value",()=>{
 const now=Date.UTC(2026,10,18,20,0),s={symbol:"EURUSD",family:"trend_pullback",side:1,bar_time:now-900000,reference_close:1.20004,atr:.0005,stop_atr:1.5,reward_r:2};
 const spec={volumeMin:.01,volumeMax:10,volumeStep:.01,digits:5,point:.00001,tickSize:.00001,tickValueAccount:1,specSource:"broker",tickValueCurrency:{code:"USD",source:"wire"},stopLevel:0};
 const out=c.preflight({signal:s,quote:{bid:1.2,ask:1.20008},spec,equity:5000,now});
 assert.equal(out.ok,true,JSON.stringify(out));assert.ok(out.risk<=12.5001);assert.ok(out.request.volume>0);assert.ok(out.request.stopLoss<1.2);
 assert.equal(c.preflight({signal:s,quote:{bid:1.2,ask:1.20008},spec:{...spec,tickValueAccount:undefined},equity:5000,now}).reason,"NATIVE_ACCOUNT_TICK_VALUE_UNVERIFIED");
 assert.equal(c.preflight({signal:s,quote:{bid:1.2,ask:1.20008},spec:{...spec,tickValueCurrency:{code:"USD",source:"heuristic"}},equity:5000,now}).ok,false);
 assert.equal(c.preflight({signal:s,quote:{bid:1.2,ask:1.3},spec,equity:5000,now}).reason,"SPREAD_TOO_WIDE");
 assert.equal(c.floorVolume(.61,{volumeMin:.25,volumeStep:.25,volumeMax:5},2),.5);
 assert.equal(c.floorVolume(.1,{volumeMin:.25,volumeStep:.25,volumeMax:5},2),0);
});
test("demo orders require exact account plus triple local authorization",()=>{
 const demo={id:"acc_demo",broker:"mt5",isDemo:true,hot:true},env={SENTINEL_CLOUD_MODE:"demo_execution",SENTINEL_CLOUD_ENABLE_DEMO:"YES_I_AUTHORIZE_SENTINEL_DEMO_ONLY",SENTINEL_CLOUD_UNVERIFIED_TRIAL:"YES_EXPLICIT_DEMO_TRIAL",SENTINEL_CLOUD_ACCOUNT_ID:"acc_demo"};
 assert.equal(c.demoExecutionAllowed(env,demo),true);
 assert.equal(c.demoExecutionAllowed(env,{...demo,isDemo:false}),false);
 assert.equal(c.demoExecutionAllowed({...env,SENTINEL_CLOUD_ACCOUNT_ID:"acc_other"},demo),false);
 assert.equal(c.demoExecutionAllowed({...env,SENTINEL_CLOUD_MODE:"research"},demo),false);
 assert.equal(c.demoExecutionAllowed({...env,SENTINEL_CLOUD_UNVERIFIED_TRIAL:""},demo),false);
});
test("provider blocks cloud trading by default, allowlists methods and sends deterministic idempotency header when armed",async()=>{
 const seen=[];
 const fake=async(url,opt)=>{seen.push({url,opt});return {ok:true,json:async()=>({status:"open",ticket:123})}};
 const p=provider("fake_test_token_1234567890",{fetcher:fake,allowWrites:false});
 await assert.rejects(()=>p.submit("acc_demo",{type:"market",symbol:"EURUSD",side:"BUY",volume:.01,stopLoss:1,takeProfit:2,comment:"STC-abc"},"a".repeat(64)),/DISABLED/);
 const armed=provider("fake_test_token_1234567890",{fetcher:fake,allowWrites:true});
 await armed.submit("acc_demo",{type:"market",symbol:"EURUSD",side:"BUY",volume:.01,stopLoss:1,takeProfit:2,comment:"STC-abc"},"a".repeat(64));
 assert.equal(seen.length,1);assert.equal(seen[0].opt.headers["Idempotency-Key"],"a".repeat(64));
 assert.equal(seen[0].opt.method,"POST");assert.ok(!seen[0].url.includes("secret"));
 await assert.rejects(()=>armed.submit("acc_demo",{type:"BUY_STOP",symbol:"EURUSD"},"a".repeat(64)),/UNSAFE/);
});
test("cloud runner remains unarmed under existing demo connection and records shadow cycles",async()=>{
 const now=Date.UTC(2026,10,18,20,0),{m,h}=signalFixture(now),seen=[],data={};
 const mRaw=m.map(x=>({...x,timestamp:x.time/1000}));const hRaw=h.map(x=>({...x,timestamp:x.time/1000}));
 const env={MT5_CLOUD_ENCRYPTION_KEY:"0".repeat(64)};
 // Cipher is generated with real AES-GCM, exactly matching the already stored key format.
 const crypto=require('node:crypto');const iv=Buffer.alloc(12,1),d=crypto.createCipheriv('aes-256-gcm',Buffer.alloc(32),iv);
 const encrypted=[iv.toString('base64'),null,Buffer.concat([d.update('connected_fake_token_12345','utf8'),d.final()]).toString('base64')];encrypted[1]=d.getAuthTag().toString('base64');
 const sql=async(strings,...vals)=>{
  const q=strings.join('?');
  if(q.includes('to_regclass'))return [{cycles:'sentinel_cloud_trader_cycles',intents:'sentinel_cloud_trader_intents',lease:'sentinel_cloud_trader_lease'}];
  if(q.includes('INSERT INTO sentinel_cloud_trader_lease'))return [{lease_owner:'lease'}];
  if(q.includes('SELECT cipher_value'))return [{cipher_value:encrypted.join('.')}];
  if(q.includes('SELECT account_id FROM sentinel_autonomy_cycles'))return [{account_id:'acc_demo'}];
  if(q.includes('SELECT signal_hash,comment FROM sentinel_cloud_trader_intents'))return [];
  if(q.includes('INSERT INTO sentinel_cloud_trader_daily'))return [{start_equity:5000}];
  if(q.includes('INSERT INTO sentinel_cloud_trader_cycles')){seen.push({kind:'record',vals});return []}
  if(q.includes('UPDATE sentinel_cloud_trader_lease'))return [];
  throw Error('unexpected SQL '+q);
 };
 const api={accounts:async()=>[{id:'acc_demo',broker:'mt5',server:'Test-Demo',isDemo:true,hot:true,accountNumber:'****1234'}],
 account:async()=>({id:'acc_demo',broker:'mt5',isDemo:true,status:'online',server:'Test-Demo',account:{accountType:'demo',equity:5000},positions:[]}),
 orders:async()=>[],symbols:async()=>({symbols:['EURUSD']}),
 candles:async(id,s,tf)=>({coverage:'complete',truncated:false,candles:tf==='M15'?mRaw:hRaw}),
 quote:async()=>({bid:m.at(-1).close-.00004,ask:m.at(-1).close+.00004}),spec:async()=>({spec:{volumeMin:.01,volumeMax:10,volumeStep:.01,digits:5,point:.00001,tickSize:.00001,tickValueAccount:1,specSource:'broker',tickValueCurrency:{code:'USD',source:'wire'},stopLevel:0}}),
 submit:async()=>{throw Error('MUST_NOT_SUBMIT_IN_RESEARCH_MODE')}};
 const r=await runCloudCycle(sql,{now,env,providerFactory:(token,opts)=>{
  assert.equal(token,'connected_fake_token_12345');assert.equal(opts.allowWrites,false);return api}});
 assert.equal(r.mode,'SHADOW_ONLY');assert.equal(r.orders_sent,0);assert.equal(r.status,'COMPLETED');assert.equal(r.observations.length,1);
 assert.equal(seen.filter(x=>x.kind==='record').length,1);
});
test("symbol mapping prefers gold, BTC, NAS and EURUSD without requiring new provider",()=>{
 assert.deepEqual(pickSymbols({symbols:['BTCUSD','GOLD','EURUSD','USTECH100M','RANDOM','BTCUSDm']}),['GOLD','BTCUSD','USTECH100M','EURUSD']);
});
