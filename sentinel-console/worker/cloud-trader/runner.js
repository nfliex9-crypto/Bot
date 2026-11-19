"use strict";
/* Sentinel's broker-connected cloud DEMO engine. Uses EXISTING encrypted
 * TickerAll token and already connected MT5 DEMO account(s).
 * Research-only by default. No browser or public trading endpoint.
 * Every ambiguous provider outcome is permanently held for reconciliation.
 */
const crypto=require("node:crypto");
const {provider}=require("./provider.js");
const c=require("./core.js");
function decrypt(cipher,key){
 if(!/^[0-9a-f]{64}$/i.test(key||""))throw Error("CLOUD_ENCRYPTION_KEY_REQUIRED");
 const parts=String(cipher||"").split(".");
 if(parts.length!==3)throw Error("INVALID_ENCRYPTED_TOKEN");
 const [iv,tag,data]=parts.map(x=>Buffer.from(x,"base64"));
 const d=crypto.createDecipheriv("aes-256-gcm",Buffer.from(key,"hex"),iv);
 d.setAuthTag(tag);
 return Buffer.concat([d.update(data),d.final()]).toString("utf8");
}
const SERVICE="sentinel-cloud-trader";
const PRIORITY=[["XAUUSD","GOLD"],["BTCUSD","BTCUSDT"],["USTECH100M","NAS100"],["EURUSD"]];
const clean=s=>String(s||"").replace(/[\x00-\x1F]/g," ").slice(0,100);
function pickSymbols(raw){
 const names=(Array.isArray(raw)?raw:raw?.symbols||[]).filter(x=>typeof x==="string"&&/^[A-Za-z0-9._#-]{2,24}$/.test(x));
 const found=[];
 for(const group of PRIORITY){
  let match=null;
  for(const base of group){
   match=names.find(s=>s.toUpperCase()===base)||names.find(s=>s.toUpperCase().startsWith(base)&&s.length<=base.length+3);
   if(match)break;
  }
  if(match&&!found.includes(match))found.push(match);
 }
 return found.slice(0,4);
}
// Prefer an existing linked Fusion MT5 Demo for shadow-only comparison after
// the owner securely links it in TickerAll. Never silently switch execution
// to a different account; demo orders still require an explicit exact ID.
function shadowPreferredDemo(roster,incumbent,env={}){
 if(env.SENTINEL_CLOUD_MODE==="demo_execution"||env.SENTINEL_CLOUD_ACCOUNT_ID)return incumbent;
 const accounts=Array.isArray(roster)?roster:(Array.isArray(roster?.accounts)?roster.accounts:[]);
 const matches=accounts.filter(a=>a?.broker==="mt5"&&a.isDemo===true&&a.hot===true&&
   a.readOnly!==true&&/fusion/i.test(String(a.server||"")+" "+String(a.name||"")));
 return matches.length===1?matches[0].id:incumbent;
}
async function tokenFromExistingSettings(sql,env){
 const keys=await sql`SELECT cipher_value FROM sentinel_mt5_cloud_config WHERE config_key='tickerall_api_token' LIMIT 1`;
 if(keys.length!==1)throw Error("EXISTING_TICKERALL_KEY_NOT_PRESENT");
 return decrypt(keys[0].cipher_value,env.MT5_CLOUD_ENCRYPTION_KEY);
}
function strictPositions(raw){if(!Array.isArray(raw))throw Error("BROKER_POSITIONS_UNKNOWN");return raw}
function strictOrders(raw){const xs=Array.isArray(raw)?raw:raw?.orders;if(!Array.isArray(xs))throw Error("BROKER_PENDING_ORDERS_UNKNOWN");return xs}
async function reconcile(sql,api,accountId,positions,knownHistory=null){
 const pending=await sql`SELECT signal_hash,comment,broker_ticket FROM sentinel_cloud_trader_intents
  WHERE account_id=${accountId} AND status IN ('SUBMITTING','UNKNOWN','ACK_PENDING_RECONCILIATION')
  ORDER BY created_at DESC LIMIT 50`;
 if(!pending.length)return {blocked:false,matched:0};
 let history=knownHistory;
 if(history===null)try{const h=await api.history(accountId);history=Array.isArray(h)?h:h?.trades}
 catch(_){} // Still block; inability to fetch history is NOT evidence of non-execution.
 let matched=0;
 for(const p of pending){
  const row=[...positions,...(Array.isArray(history)?history:[])].find(x=>
   x&&String(x.ticket||"").length>0&&(
      String(x.comment||"")===String(p.comment||"")||
      (p.broker_ticket&&String(x.ticket)===String(p.broker_ticket))));
  if(row){await sql`UPDATE sentinel_cloud_trader_intents
     SET status='BROKER_POSITION_OR_HISTORY_CONFIRMED',broker_ticket=${String(row.ticket)},updated_at=NOW()
     WHERE signal_hash=${p.signal_hash} AND account_id=${accountId}`;matched++}
 }
 // After a confirmed order, max-position guard is still necessary. No automatic re-entry
 // on the same signal due to UNIQUE(account_id,signal_hash) journal entry.
 return {blocked:pending.length>matched,matched};
}
async function syncClosedFills(sql,accountId,accountCurrency,history){
 if(!Array.isArray(history)||!/^[A-Z]{3}$/.test(String(accountCurrency||"")))return 0;
 const owned=await sql`SELECT signal_hash,broker_ticket,symbol,family FROM sentinel_cloud_trader_intents
    WHERE account_id=${accountId} AND broker_ticket IS NOT NULL AND broker_ticket<>'' LIMIT 200`;
 const byTicket=new Map(owned.map(x=>[String(x.broker_ticket),x]));
 let recorded=0;
 for(const row of history){
  const mine=byTicket.get(String(row?.ticket||""));
  if(!mine||row.complete!==true||row.partial===true||String(row.symbol)!==mine.symbol)continue;
  const value=Number(row.profit),swap=Number(row.swap),commission=Number(row.commission);
  const date=Date.parse(String(row.closeTime||""));
  if([row.profit,row.swap,row.commission].some(x=>x===null||x===undefined)||
     ![value,swap,commission].every(Number.isFinite)||!Number.isFinite(date))continue;
  await sql`INSERT INTO sentinel_cloud_trader_fills
    (account_id,signal_hash,broker_ticket,symbol,family,close_time,currency,profit,swap,commission,verified_at)
    VALUES(${accountId},${mine.signal_hash},${String(row.ticket)},${mine.symbol},${mine.family},
    ${new Date(date).toISOString()},${accountCurrency},${value},${swap},${commission},NOW())
    ON CONFLICT(account_id,broker_ticket) DO UPDATE SET
     profit=EXCLUDED.profit,swap=EXCLUDED.swap,commission=EXCLUDED.commission,
     verified_at=NOW()`;
  recorded++;
 }
 return recorded;
}
async function recordCycle(sql,record){
 await sql`INSERT INTO sentinel_cloud_trader_cycles
  (cycle_id,account_id,account_last4,mode,status,reason,observations,orders_sent,observed_at)
  VALUES(${record.cycle_id},${record.account_id||null},${record.account_last4||null},
   ${record.mode},${record.status},${record.reason},${JSON.stringify(record.observations||[])}::jsonb,
   ${record.orders_sent||0},NOW())`;
}
async function runCloudCycle(sql,{now=Date.now(),env=process.env,fetcher=fetch,providerFactory=provider}={}){
 const cycle_id=crypto.randomUUID(),owner=crypto.randomUUID();
 const report={cycle_id,account_id:null,account_last4:null,mode:"SHADOW_ONLY",status:"COLLECTING",reason:"",observations:[],orders_sent:0};
 const tables=await sql`SELECT to_regclass('public.sentinel_cloud_trader_cycles') AS cycles,
  to_regclass('public.sentinel_cloud_trader_intents') AS intents,
  to_regclass('public.sentinel_cloud_trader_fills') AS fills,
  to_regclass('public.sentinel_cloud_trader_lease') AS lease`;
 if(!tables[0]?.cycles||!tables[0]?.intents||!tables[0]?.lease||!tables[0]?.fills)return {...report,status:"MIGRATION_REQUIRED"};
 const lease=await sql`INSERT INTO sentinel_cloud_trader_lease(worker_name,lease_owner,lease_until)
 VALUES(${SERVICE},${owner},NOW()+INTERVAL '5 minutes') ON CONFLICT(worker_name) DO UPDATE SET
 lease_owner=EXCLUDED.lease_owner,lease_until=EXCLUDED.lease_until
 WHERE sentinel_cloud_trader_lease.lease_until<NOW() RETURNING lease_owner`;
 if(!lease.length)return {...report,status:"LEASE_BUSY"};
 try{
  const token=await tokenFromExistingSettings(sql,env);
  // Even when local flags are set, provider permits writes only after verifying
  // a specific HOT MT5 DEMO account against the already established connection.
  const read=providerFactory(token,{fetcher,allowWrites:false});
  const roster=await read.accounts();
  const recent=await sql`SELECT account_id FROM sentinel_autonomy_cycles WHERE account_id IS NOT NULL
    ORDER BY started_at DESC LIMIT 1`;
  const explicit=env.SENTINEL_CLOUD_ACCOUNT_ID||"";
  const preferred=shadowPreferredDemo(roster,recent[0]?.account_id||"",env);
  const chosen=c.selectAccount(roster,explicit,preferred);
  if(!chosen.account){report.status="BLOCKED";report.reason=chosen.status;return report}
  const a=chosen.account;
  report.account_id=a.id;report.account_last4=String(a.accountNumber||"").slice(-4);
  const account=await read.account(a.id);
  if(account?.id!==a.id||account.broker!=="mt5"||account.isDemo!==true||account.status!=="online"||account.account?.accountType!=="demo"||account.readOnly===true||a.readOnly===true){
   report.status="BLOCKED";report.reason="BROKER_DEMO_ACCOUNT_VALIDATION_FAILED";return report
  }
  if(account.server&&String(account.server)!==String(a.server||"")){
   report.status="BLOCKED";report.reason="ACCOUNT_SERVER_CHANGED";return report
  }
  const equity=Number(account.account?.equity);
  if(!Number.isFinite(equity)||equity<=0){report.status="BLOCKED";report.reason="EQUITY_NOT_AVAILABLE";return report}
  const positions=strictPositions(account.positions),orders=strictOrders(await read.orders(a.id));
  let brokerHistory=null;
  try{const h=await read.history(a.id);brokerHistory=Array.isArray(h)?h:h?.trades}catch(_){}
  const unresolved=await reconcile(sql,read,a.id,positions,brokerHistory);
  if(Array.isArray(brokerHistory)){
   try{report.fills_verified=await syncClosedFills(sql,a.id,account.account.currency,brokerHistory)}
   catch(e){report.fill_sync_error=clean(e.message)}
  }
  if(unresolved.blocked){report.status="BLOCKED";report.reason="UNKNOWN_ORDER_REQUIRES_RECONCILIATION";return report}
  const utcDay=new Date(now).toISOString().slice(0,10);
  const baseline=await sql`INSERT INTO sentinel_cloud_trader_daily(account_id,utc_day,start_equity)
   VALUES(${a.id},${utcDay},${equity}) ON CONFLICT(account_id,utc_day) DO UPDATE SET
   start_equity=sentinel_cloud_trader_daily.start_equity RETURNING start_equity`;
  const start=Number(baseline[0]?.start_equity);
  if(!(start>0)||equity<start*.99){report.status="BLOCKED";report.reason="DAILY_LOSS_LIMIT";return report}
  const catalog=await read.symbols(a.id),symbols=pickSymbols(catalog);
  if(!symbols.length){report.status="BLOCKED";report.reason="BROKER_SYMBOLS_NOT_FOUND";return report}
  // Triple gate: connection verified DEMO, exact linked account selected, and
  // explicit two-stage local trial authorization. This is not an approved alpha.
  const enabled=c.demoExecutionAllowed(env,a);
  report.mode=enabled?"UNVERIFIED_DEMO_TRIAL":"SHADOW_ONLY";
  if(enabled&&(!explicit||String(explicit)!==String(a.id))){report.status="BLOCKED";report.reason="ACCOUNT_ID_NOT_EXPLICITLY_SELECTED";return report}
  const write=enabled?providerFactory(token,{fetcher,allowWrites:true}):null;
  // Sample only closed broker bars. Never substitute stored partial research bars
  // for an unavailable broker feed when deciding a live DEMO entry.
  for(const symbol of symbols){
   const row={symbol,status:"NO_SIGNAL_OR_UNAVAILABLE",trades_submitted:0};
   report.observations.push(row);
   try{
    const [rawM,rawH]=await Promise.all([read.candles(a.id,symbol,"M15",40),read.candles(a.id,symbol,"H1",100)]);
    if(rawM?.truncated===true||rawH?.truncated===true||rawM?.coverage!=="complete"||rawH?.coverage!=="complete"){
     row.status="HISTORY_NOT_COMPLETE";continue
    }
    const m15=c.parseCandles(rawM.candles,"M15",now),h1=c.parseCandles(rawH.candles,"H1",now);
    const signal=c.decide(symbol,m15,h1,now);
    if(!signal){row.status="NO_VALID_CLOSED_BAR_SIGNAL";continue}
    row.signal_hash=c.keyFor(a.id,signal).slice(0,20);
    // Actual Sentinel brain research registry is consulted, but an
    // OHLC hypothesis or paper candidate is NEVER self-approved as alpha.
    const candidates=await sql`SELECT candidate_id,status FROM sentinel_autonomy_candidates
      WHERE account_id=${a.id} AND symbol=${symbol} AND timeframe='M15' AND family=${signal.family}
      ORDER BY last_evaluated_at DESC LIMIT 3`;
    row.brain_status=candidates.length?"RESEARCH_CANDIDATE_UNVERIFIED":"NO_VERIFIED_BRAIN_EVIDENCE";
    row.side=signal.side===1?"LONG":"SHORT";row.strategy=signal.family;
    if(positions.length||orders.length){row.status="ACCOUNT_HAS_EXISTING_POSITION_OR_ORDER";continue}
    const [quote,specResult]=await Promise.all([read.quote(a.id,symbol),read.spec(a.id,symbol)]);
    const ready=c.preflight({signal,quote,spec:specResult.spec,equity,now});
    if(!ready.ok){row.status=ready.reason;continue}
    row.risk_at_stop=Number(ready.risk.toFixed(2));
    if(!enabled){row.status="SHADOW_SIGNAL_RESEARCH_NOT_APPROVED";continue}
    // The engine is deliberately a controlled unverified DEMO trial, never
    // automatically promoted from Sentinel's unverified OHLC hypotheses.
    const digest=c.keyFor(a.id,signal),comment="STC-"+digest.slice(0,16);
    const reservation=await sql`INSERT INTO sentinel_cloud_trader_intents
     (account_id,signal_hash,symbol,family,side,bar_time,comment,status)
     VALUES(${a.id},${digest},${symbol},${signal.family},${row.side},${new Date(signal.bar_time).toISOString()},
     ${comment},'RESERVED') ON CONFLICT(account_id,signal_hash) DO NOTHING RETURNING signal_hash`;
    if(!reservation.length){row.status="SIGNAL_ALREADY_RESERVED";continue}
    // Re-check immediately before broker submission; do not rely on a stale
    // position snapshot taken before candle/spec requests.
    const [latestAccount,latestOrders]=await Promise.all([read.account(a.id),read.orders(a.id)]);
    if(latestAccount?.id!==a.id||latestAccount?.isDemo!==true||latestAccount?.status!=="online"||
       latestAccount.account?.accountType!=="demo"||strictPositions(latestAccount.positions).length||
       strictOrders(latestOrders).length){
      row.status="STATE_CHANGED_BEFORE_ORDER";
      await sql`UPDATE sentinel_cloud_trader_intents SET status='NOT_SENT',updated_at=NOW()
       WHERE account_id=${a.id} AND signal_hash=${digest}`;
      break;
    }
    await sql`UPDATE sentinel_cloud_trader_intents SET status='SUBMITTING',updated_at=NOW()
     WHERE signal_hash=${digest} AND account_id=${a.id}`;
    try{
     const placed=await write.submit(a.id,{...ready.request,comment},digest);
     // Even a provider 201 only proves its response, not a confirmed booked
     // broker deal. Reconciliation will check matching broker comment/ticket.
     row.status="ACK_PENDING_RECONCILIATION";row.trades_submitted=1;report.orders_sent++;
     await sql`UPDATE sentinel_cloud_trader_intents SET status='ACK_PENDING_RECONCILIATION',
      broker_ticket=${String(placed?.ticket||"")},updated_at=NOW() WHERE account_id=${a.id} AND signal_hash=${digest}`;
    }catch(e){
     // Explicit errors and ambiguous timeouts are both terminal here: no retry.
     row.status="BROKER_OUTCOME_UNKNOWN";
     await sql`UPDATE sentinel_cloud_trader_intents SET status='UNKNOWN',updated_at=NOW(),
      error_code=${clean(e.message)} WHERE account_id=${a.id} AND signal_hash=${digest}`;
    }
    // One logical trial order at most per cycle.
    break;
   }catch(e){row.status="DATA_OR_PREFLIGHT_ERROR";row.error_code=clean(e.message)}
  }
  // A successful account login does not mean market-data requests succeeded.
  // Surface a degraded condition when all eligible broker candle requests fail.
  if(report.observations.length>0&&report.observations.every(x=>x.status==="DATA_OR_PREFLIGHT_ERROR")){
    report.status="MARKET_DATA_UNAVAILABLE";
    report.reason="ALL_BROKER_CANDLE_REQUESTS_FAILED";
    return report;
  }
  if(report.observations.length>0&&report.observations.every(x=>["DATA_OR_PREFLIGHT_ERROR","HISTORY_NOT_COMPLETE"].includes(x.status))){
    report.status="MARKET_HISTORY_INCOMPLETE";
    report.reason="CLOSED_BAR_HISTORY_NOT_READY";
    return report;
  }
  report.status="COMPLETED";report.reason=enabled?"INDEPENDENT_MT5_DEMO_TRIAL":"BROKER_SHADOW_RESEARCH_ONLY";
  return report;
 }catch(e){report.status="ERROR";report.reason=clean(e.message);return report}
 finally{
  try{await recordCycle(sql,report)}catch(e){console.error("sentinel_cloud_trader_record_failure",clean(e.message))}
  try{await sql`UPDATE sentinel_cloud_trader_lease SET lease_until=NOW()
   WHERE worker_name=${SERVICE} AND lease_owner=${owner}`}catch(_){}
 }
}
module.exports={runCloudCycle,pickSymbols,shadowPreferredDemo,strictPositions,strictOrders,reconcile,syncClosedFills};
