"use strict";
const crypto=require("node:crypto");
const {neon}=require("@neondatabase/serverless");
const core=require("../brain/engine.js");
const {fingerprint}=require("../brain/provenance.js");
const factory=require("../brain/strategy-factory.js");
const {researchRadar}=require("../brain/research-radar.js");
const SERVICE="sentinel-autonomy";
const API="https://api.tickerall.com";
function clean(x){return String(x??"").replace(/[\r\n\x00-\x1f]/g," ").slice(0,120)}
function decrypt(cipher,key){
 if(!/^[0-9a-f]{64}$/i.test(key||""))throw Error("ENCRYPTION_KEY_REQUIRED");
 const [iv,tag,data]=String(cipher||"").split(".").map(x=>Buffer.from(x,"base64"));
 if(!iv||!tag||!data)throw Error("INVALID_SECRET_FORMAT");
 const d=crypto.createDecipheriv("aes-256-gcm",Buffer.from(key,"hex"),iv);
 d.setAuthTag(tag);return Buffer.concat([d.update(data),d.final()]).toString("utf8");
}
async function fetchJSON(url,headers={}){
 const u=new URL(url);
 if(u.protocol!=="https:"||!((u.hostname==="api.tickerall.com"&&/^\/v1\/accounts(?:\/[A-Za-z0-9_-]{3,128}(?:\/(?:symbols|candles|history))?)?$/.test(u.pathname))||(u.hostname==="api.crossref.org"&&u.pathname==="/works")))throw Error("SOURCE_NOT_ALLOWLISTED");
 const response=await fetch(u,{headers:{Accept:"application/json",...headers},redirect:"error",cache:"no-store",signal:AbortSignal.timeout(12000)});
 if(!response.ok)throw Error((u.hostname==="api.tickerall.com"?"BROKER_HTTP_":"RESEARCH_HTTP_")+response.status);
 return response.json();
}
function selectMarkets(payload,now){
 const symbols=(Array.isArray(payload?.symbols)?payload.symbols:[]).filter(s=>typeof s==="string"&&/^[A-Za-z0-9._#-]{2,24}$/.test(s));
 const weekend=[0,6].includes(now.getUTCDay());
 return [
  ["gold",/^(XAUUSD|GOLD)([._#-]?[A-Za-z0-9]+)?$/i],
  ["btc",/^BTCUSD([._#-]?[A-Za-z0-9]+)?$/i],
  ["eurusd",/^EURUSD([._#-]?[A-Za-z0-9]+)?$/i],
  ["nasdaq",/^(NAS100|US100|USTEC)([._#-]?[A-Za-z0-9]+)?$/i]
 ].filter(([name])=>!weekend||name==="btc").map(([,p])=>symbols.find(s=>p.test(s))).filter(Boolean).slice(0,4);
}
async function saveBars(sql,account,symbol,tf,source){
 const bars=core.normalizeCandles(Array.isArray(source.candles)?source.candles:[]).bars.slice(-10000);
 if(!bars.length)return [];
 const j=JSON.stringify(bars.map(b=>({bar_time:new Date(b.timestamp).toISOString(),open:b.open,high:b.high,low:b.low,close:b.close,spread:b.spread,tick_volume:b.tickVolume})));
 await sql`INSERT INTO sentinel_brain_candles(account_id,symbol,timeframe,bar_time,open,high,low,close,spread,tick_volume)
 SELECT ${account},${symbol},${tf},r.bar_time,r.open,r.high,r.low,r.close,r.spread,r.tick_volume
 FROM jsonb_to_recordset(${j}::jsonb) AS r(bar_time timestamptz,open numeric,high numeric,low numeric,close numeric,spread numeric,tick_volume numeric)
 ON CONFLICT(account_id,symbol,timeframe,bar_time) DO UPDATE SET open=EXCLUDED.open,high=EXCLUDED.high,low=EXCLUDED.low,close=EXCLUDED.close,spread=EXCLUDED.spread,tick_volume=EXCLUDED.tick_volume,fetched_at=NOW()`;
 await sql`INSERT INTO sentinel_brain_imports(account_id,symbol,timeframe,requested_hours,provider_count,coverage,truncated,stop_reason,imported_at)
 VALUES(${account},${symbol},${tf},${tf==="M15"?1440:3000},${bars.length},${String(source.coverage||"unknown")},${source.truncated===true},${String(source.stopReason||"")},NOW())
 ON CONFLICT(account_id,symbol,timeframe) DO UPDATE SET provider_count=EXCLUDED.provider_count,coverage=EXCLUDED.coverage,
 truncated=EXCLUDED.truncated,stop_reason=EXCLUDED.stop_reason,imported_at=NOW()`;
 return bars;
}
async function cacheBars(sql,account,symbol,tf){
 const rows=await sql`SELECT bar_time,open,high,low,close,spread,tick_volume
 FROM sentinel_brain_candles WHERE account_id=${account} AND symbol=${symbol} AND timeframe=${tf}
 ORDER BY bar_time DESC LIMIT 9500`;
 return rows.reverse().map(r=>({timestamp:new Date(r.bar_time).getTime(),open:Number(r.open),high:Number(r.high),
 low:Number(r.low),close:Number(r.close),spread:r.spread===null?null:Number(r.spread),
 tickVolume:r.tick_volume===null?null:Number(r.tick_volume)}));
}
async function assess(sql,{account,symbol,tf,bars,coverage,truncated,cycleId,now}){
 const old=await sql`SELECT spec FROM sentinel_autonomy_candidates WHERE account_id=${account} AND symbol=${symbol}
 AND timeframe=${tf} AND status IN ('BOOST_PAPER_RESEARCH_2X','OBSERVE_MORE')
 ORDER BY reward_points DESC,last_evaluated_at DESC LIMIT 5`;
 const parents=old.length?old.map(r=>r.spec):factory.seeds().slice(0,6);
 const result=factory.scoreFamily(bars,{coverage,truncated,cycleId:now.toISOString().slice(0,10),parents});
 if(!result.candidates.length)return {symbol,tf,status:result.status,reason:result.reason,candidates:0};
 const fp=fingerprint(core.normalizeCandles(bars).bars,{symbol,timeframe:tf,coverage});
 for(const c of result.candidates){
  const id=crypto.createHash("sha256").update(account+"|"+symbol+"|"+tf+"|"+c.id).digest("hex");
  const spec=JSON.stringify(c.spec),metrics=JSON.stringify({...c,dataset:fp,cycleId});
  const isReward=c.status==="BOOST_PAPER_RESEARCH_2X";
  await sql`INSERT INTO sentinel_autonomy_candidates(candidate_id,account_id,symbol,timeframe,family,spec,status,metrics,dataset_id,reward_points,last_reward_at)
  VALUES(${id},${account},${symbol},${tf},${c.family},${spec}::jsonb,${c.status},${metrics}::jsonb,${fp.id},${isReward?1:0},${isReward?now.toISOString():null})
  ON CONFLICT(candidate_id) DO UPDATE SET status=EXCLUDED.status,metrics=EXCLUDED.metrics,dataset_id=EXCLUDED.dataset_id,
  evaluated_cycles=sentinel_autonomy_candidates.evaluated_cycles+1,last_evaluated_at=NOW(),
  reward_points=CASE WHEN EXCLUDED.status='BOOST_PAPER_RESEARCH_2X'
   AND sentinel_autonomy_candidates.dataset_id<>EXCLUDED.dataset_id
   AND (sentinel_autonomy_candidates.last_reward_at IS NULL OR sentinel_autonomy_candidates.last_reward_at<NOW()-INTERVAL '7 days')
   THEN sentinel_autonomy_candidates.reward_points+1 ELSE sentinel_autonomy_candidates.reward_points END,
  last_reward_at=CASE WHEN EXCLUDED.status='BOOST_PAPER_RESEARCH_2X'
   AND sentinel_autonomy_candidates.dataset_id<>EXCLUDED.dataset_id
   AND (sentinel_autonomy_candidates.last_reward_at IS NULL OR sentinel_autonomy_candidates.last_reward_at<NOW()-INTERVAL '7 days')
   THEN NOW() ELSE sentinel_autonomy_candidates.last_reward_at END`;
 }
 return {symbol,tf,status:"RESEARCH_ONLY",candidates:result.candidates.length,rewarded:result.rewarded,
 retired:result.retired,source_rows:bars.length,dataset_id:fp.id};
}
async function harvest(sql,now,fetcher){
 if(![4,16].includes(now.getUTCHours()))return {status:"NOT_DUE"};
 const x=await researchRadar({fetchJSON:fetcher});
 for(const p of x.items)await sql`INSERT INTO sentinel_autonomy_papers(doi,title,published_year,topic,source_url,source_kind)
 VALUES(${p.doi},${p.title},${p.year},${p.topic},${p.source_url},${p.source_kind})
 ON CONFLICT(doi) DO UPDATE SET last_seen_at=NOW()`;
 return {status:x.failures.length?"PARTIAL":"DONE",papers:x.items.length};
}
async function researchCycle(sql,{now=new Date(),fetcher=fetchJSON}={}){
 const id=crypto.randomUUID(),results=[],notes={};let status="COMPLETED",accountId=null;
 await sql`INSERT INTO sentinel_autonomy_cycles(cycle_id,status) VALUES(${id},'RUNNING')`;
 try{
  const config=await sql`SELECT cipher_value FROM sentinel_mt5_cloud_config WHERE config_key='tickerall_api_token' LIMIT 1`;
  let token=null,roster=[];
  if(config.length)try{
   token=decrypt(config[0].cipher_value,process.env.MT5_CLOUD_ENCRYPTION_KEY);
   roster=await fetcher(API+"/v1/accounts",{Authorization:"Bearer "+token});
  }catch(e){notes.broker_error=clean(e.message)}
  else notes.broker_error="TICKERALL_KEY_UNCONFIGURED";
  const accounts=Array.isArray(roster)?roster:(roster?.accounts||[]);
  const demo=accounts.find(a=>a.broker==="mt5"&&a.isDemo===true&&a.hot===true
   &&["CONNECTED","ONLINE"].includes(String(a.status).toUpperCase())
   &&/^[A-Za-z0-9_-]{3,128}$/.test(String(a.id)));
  accountId=demo?.id||null;let symbols=[];
  if(demo)try{
   symbols=selectMarkets(await fetcher(API+"/v1/accounts/"+demo.id+"/symbols",{Authorization:"Bearer "+token}),now);
  }catch(e){notes.symbol_error=clean(e.message)}
  if(symbols.length){
   for(const symbol of symbols)for(const tf of ["M15","H1"])try{
    const last=await sql`SELECT imported_at FROM sentinel_brain_imports
     WHERE account_id=${demo.id} AND symbol=${symbol} AND timeframe=${tf}`;
    if(last.length&&now.getTime()-new Date(last[0].imported_at).getTime()<7200000){
     results.push({symbol,tf,status:"HISTORY_REFRESH_NOT_DUE"});continue;
    }
    const url=API+"/v1/accounts/"+demo.id+"/candles?"+new URLSearchParams({
      symbol,timeframe:tf,hours:String(tf==="M15"?1440:3000)
    });
    const response=await fetcher(url,{Authorization:"Bearer "+token});
    const bars=await saveBars(sql,demo.id,symbol,tf,response);
    if(!bars.length){results.push({symbol,tf,status:"NO_BARS"});continue}
    results.push(await assess(sql,{account:demo.id,symbol,tf,bars,coverage:response.coverage,
      truncated:response.truncated,cycleId:id,now}));
   }catch(e){results.push({symbol,tf,status:"ERROR",error:clean(e.message)})}
  }else{
   notes.mode="CACHED_BROKER_REPLAY_ONLY";
   const cached=await sql`SELECT account_id,symbol,timeframe,MAX(bar_time) AS last_bar
    FROM sentinel_brain_candles GROUP BY account_id,symbol,timeframe ORDER BY MAX(bar_time) DESC LIMIT 8`;
   for(const row of cached)try{
    const bars=await cacheBars(sql,row.account_id,row.symbol,row.timeframe);
    if(bars.length<900)continue;
    results.push(await assess(sql,{account:row.account_id,symbol:row.symbol,
      tf:row.timeframe,bars,coverage:"complete",truncated:false,cycleId:id,now}));
   }catch(e){results.push({symbol:row.symbol,tf:row.timeframe,status:"ERROR",error:clean(e.message)})}
  }
  notes.weekend=[0,6].includes(now.getUTCDay());
  notes.demo_session_online=Boolean(demo);
  try{notes.literature=await harvest(sql,now,fetcher)}catch(e){notes.literature_error=clean(e.message)}
  if(!demo&&!results.length)status="WAITING_FOR_REAL_DATA";
  else if(results.some(r=>r.status==="ERROR"))status="PARTIAL";
 }catch(e){status="ERROR";notes.error=clean(e.message)}
 const totals={markets:results.length,candidates:results.reduce((n,r)=>n+(r.candidates||0),0),
  rewarded:results.reduce((n,r)=>n+(r.rewarded||0),0),retired:results.reduce((n,r)=>n+(r.retired||0),0)};
 await sql`UPDATE sentinel_autonomy_cycles SET finished_at=NOW(),status=${status},account_id=${accountId},
  markets_checked=${JSON.stringify(results)}::jsonb,totals=${JSON.stringify(totals)}::jsonb,
  notes=${JSON.stringify(notes)}::jsonb,error_code=${notes.error||null} WHERE cycle_id=${id}`;
 return {id,status,totals,notes,orders_executed:0};
}
async function runOnce(sql,{now=new Date(),fetcher=fetchJSON}={}){
 const owner=crypto.randomUUID();
 const locked=await sql`INSERT INTO sentinel_autonomy_worker_state(worker_name,lease_owner,lease_expires_at,last_heartbeat_at,status)
  VALUES(${SERVICE},${owner},NOW()+INTERVAL '20 minutes',NOW(),'RUNNING')
  ON CONFLICT(worker_name) DO UPDATE SET lease_owner=EXCLUDED.lease_owner,lease_expires_at=EXCLUDED.lease_expires_at,
   last_heartbeat_at=NOW(),status='RUNNING'
  WHERE sentinel_autonomy_worker_state.lease_expires_at IS NULL
    OR sentinel_autonomy_worker_state.lease_expires_at<NOW() RETURNING worker_name`;
 if(!locked.length)return {status:"LEASE_BUSY",orders_executed:0};
 try{
  const r=await researchCycle(sql,{now,fetcher});
  await sql`UPDATE sentinel_autonomy_worker_state SET
   lease_expires_at=NOW(),status=${r.status},last_cycle_id=${r.id},last_heartbeat_at=NOW(),
   last_success_at=CASE WHEN ${r.status==="COMPLETED"} THEN NOW() ELSE last_success_at END,
   last_error=${r.notes.error||r.notes.broker_error||null},updated_at=NOW()
   WHERE worker_name=${SERVICE} AND lease_owner=${owner}`;
  return r;
 }catch(e){
  const code=clean(e.message);
  await sql`UPDATE sentinel_autonomy_worker_state SET status='ERROR',last_error=${code},
   lease_expires_at=NOW(),updated_at=NOW() WHERE worker_name=${SERVICE} AND lease_owner=${owner}`;
  return {status:"ERROR",code,orders_executed:0};
 }
}
async function main(){
 if(!process.env.DATABASE_URL)throw Error("DATABASE_URL_REQUIRED");
 const sql=neon(process.env.DATABASE_URL);
 let stop=false;process.on("SIGTERM",()=>stop=true);process.on("SIGINT",()=>stop=true);
 console.log(JSON.stringify({service:SERVICE,event:"started",mode:"RESEARCH_ONLY",orders_enabled:false}));
 while(!stop){
  const started=Date.now();
  try{const r=await runOnce(sql);console.log(JSON.stringify({event:"research_cycle",status:r.status,totals:r.totals||{},orders_executed:0}))}
  catch(e){console.error(JSON.stringify({event:"worker_error",code:clean(e.message)}))}
  await new Promise(resolve=>setTimeout(resolve,Math.max(30000,900000-(Date.now()-started))));
 }
}
if(require.main===module)main().catch(e=>{console.error(clean(e.message));process.exitCode=1});
module.exports={decrypt,fetchJSON,selectMarkets,researchCycle,runOnce,assess,harvest};
