"use strict";
/**
 * Private SSO-protected READ ONLY command-center feed.
 * Truth is sourced from Neon broker journals + research worker: no market orders,
 * no simulated equity curves, no fabricated quotes or strategy profitability.
 */
const {neon}=require("@neondatabase/serverless");
const amtCurriculum=require("../brain/amt-curriculum.js");
const pdfCurriculum=require("../brain/pdf-curriculum.js");
function send(res,status,body){
  res.setHeader("Cache-Control","private, no-store, max-age=0");
  res.setHeader("X-Content-Type-Options","nosniff");
  res.setHeader("Cross-Origin-Resource-Policy","same-origin");
  return res.status(status).json(body);
}
function allowed(req){
  const host=String(req.headers.host||"").toLowerCase();
  return req.method==="GET"&&process.env.SENTINEL_VERCEL_SSO==="enabled"&&
    /^sentinel-mt5-console(?:-[a-z0-9-]+)?\.vercel\.app$/.test(host);
}
function ageSeconds(x,now){
  const timestamp=Date.parse(String(x||""));
  return Number.isFinite(timestamp)?Math.max(0,Math.floor((now-timestamp)/1000)):null;
}
function numeric(x){
  if(x===null||x===undefined||x==="")return null;
  const n=Number(x);return Number.isFinite(n)?n:null;
}
function sanitizedObservation(x){
  if(!x||typeof x!=="object")return null;
  return {symbol:String(x.symbol||"").slice(0,24),status:String(x.status||"UNKNOWN").slice(0,70),
    side:x.side?String(x.side).slice(0,8):null,
    strategy:x.strategy?String(x.strategy).slice(0,70):null,
    quote_ready:x.quote_ready===true,
    contract_status:String(x.contract_status||"NOT_CHECKED").slice(0,70),
    spread_bps:numeric(x.spread_bps),
    trades_submitted:Number(x.trades_submitted)||0,
    risk_at_stop:numeric(x.risk_at_stop),
    brain_status:x.brain_status?String(x.brain_status).slice(0,70):null};
}
module.exports=async function liveHandler(req,res){
  if(req.method!=="GET")return send(res,405,{ok:false,error:"READ_ONLY"});
  if(!allowed(req))return send(res,403,{ok:false,error:"PRIVATE_SSO_REQUIRED"});
  if(!process.env.DATABASE_URL)return send(res,503,{ok:false,error:"DATABASE_UNAVAILABLE"});
  try{
    const sql=neon(process.env.DATABASE_URL),now=Date.now();
    const [trader,brain]=await Promise.all([
      sql`SELECT cycle_id,account_id,account_last4,mode,status,reason,
         orders_sent,observed_at,observations
         FROM sentinel_cloud_trader_cycles ORDER BY observed_at DESC LIMIT 1`,
      sql`SELECT started_at,finished_at,status,totals,notes,markets_checked
         FROM sentinel_autonomy_cycles ORDER BY started_at DESC LIMIT 1`
    ]);
    const last=trader[0]||null,research=brain[0]||null;
    if(!last)return send(res,200,{ok:true,generated_at:new Date(now).toISOString(),
      mode:"READ_ONLY",account:null,health:{trader:"NOT_STARTED",brain:research?.status||"NOT_STARTED"},
      trades:{intents:0,closed:0,net:null,currency:null,recent:[]},markets:[],events:[]});
    const accountId=String(last.account_id||"");
    const [intents,fills,quotes,counts,auth,totalsByCurrency,scanHistory,researchHistory,edgeRuns]=await Promise.all([
      sql`SELECT signal_hash,symbol,family,side,status,created_at,updated_at,
          CASE WHEN broker_ticket IS NULL THEN false ELSE true END AS broker_ticket_recorded
          FROM sentinel_cloud_trader_intents WHERE account_id=${accountId}
          ORDER BY created_at DESC LIMIT 12`,
      sql`SELECT f.symbol,f.family,f.close_time,f.currency,f.profit,f.swap,f.commission,
          f.broker_ticket,i.side
          FROM sentinel_cloud_trader_fills f
          JOIN sentinel_cloud_trader_intents i
           ON i.account_id=f.account_id AND i.signal_hash=f.signal_hash
          WHERE f.account_id=${accountId}
          ORDER BY f.close_time DESC LIMIT 30`,
      sql`SELECT symbol,observed_at,bid,ask,spread FROM sentinel_autonomy_spread_observations
          WHERE account_id=${accountId} AND observed_at>NOW()-INTERVAL '12 hours'
          ORDER BY observed_at DESC LIMIT 520`,
      sql`SELECT
           (SELECT COUNT(*)::int FROM sentinel_cloud_trader_intents WHERE account_id=${accountId}) AS order_intents,
           (SELECT COUNT(*)::int FROM sentinel_cloud_trader_fills WHERE account_id=${accountId}) AS closed_fills,
           (SELECT COUNT(*)::int FROM sentinel_autonomy_candidates WHERE account_id=${accountId}) AS candidates,
           (SELECT COUNT(*)::int FROM sentinel_autonomy_cycles WHERE started_at>NOW()-INTERVAL '24 hours') AS research_cycles_24h,
           (SELECT COUNT(*)::int FROM sentinel_cloud_trader_cycles WHERE observed_at>NOW()-INTERVAL '24 hours'
             AND account_id=${accountId}) AS trade_cycles_24h,
           (SELECT COUNT(*)::int FROM sentinel_brain_runs WHERE account_id=${accountId}) AS verified_brain_runs`,
      sql`SELECT enabled,expires_at,risk_pct FROM sentinel_cloud_trader_authorizations
          WHERE account_id=${accountId} LIMIT 1`,
      sql`SELECT currency,COUNT(*)::int AS trades,
          SUM(profit+swap+commission) AS net
          FROM sentinel_cloud_trader_fills WHERE account_id=${accountId}
          GROUP BY currency ORDER BY currency`,
      sql`SELECT observed_at,status,mode,orders_sent,reason,observations
          FROM sentinel_cloud_trader_cycles WHERE account_id=${accountId}
          ORDER BY observed_at DESC LIMIT 18`,
      sql`SELECT started_at,finished_at,status,totals,markets_checked
          FROM sentinel_autonomy_cycles WHERE account_id=${accountId}
          ORDER BY started_at DESC LIMIT 8`,
      sql`SELECT symbol,version,evaluated_at,report
          FROM sentinel_edge_lab_runs WHERE account_id=${accountId}
          ORDER BY evaluated_at DESC LIMIT 16`
    ]);
    const sumByCurrency=new Map(totalsByCurrency.map(x=>[x.currency,numeric(x.net)]));
    const cleanFills=fills.map(f=>{
      const profit=numeric(f.profit),swap=numeric(f.swap),commission=numeric(f.commission);
      const net=[profit,swap,commission].every(v=>v!==null)?profit+swap+commission:null;
      return {symbol:String(f.symbol||"").slice(0,24),family:String(f.family||"").slice(0,70),
        side:String(f.side||"UNKNOWN").slice(0,8),
        closed_at:f.close_time,currency:f.currency,net,
        profit,swap,commission,ticket:String(f.broker_ticket||"").slice(-6)};
    });
    const series=new Map();
    // Observations are samples, NOT a real-time tick stream.
    for(const q of quotes.slice().reverse()){
      if(!series.has(q.symbol))series.set(q.symbol,[]);
      const bid=numeric(q.bid),ask=numeric(q.ask),spread=numeric(q.spread);
      if(bid===null||ask===null||ask<bid)continue;
      series.get(q.symbol).push({at:q.observed_at,bid,ask,spread,
        mid:(bid+ask)/2,spread_bps:((ask-bid)/((ask+bid)/2))*10000});
    }
    const observations=(Array.isArray(last.observations)?last.observations:[])
      .map(sanitizedObservation).filter(Boolean);
    const markets=observations.map(s=>{
      const samples=(series.get(s.symbol)||[]).slice(-130),quote=samples[samples.length-1]||null;
      const isFresh=quote&&ageSeconds(quote.at,now)<=600;
      return {...s,quote:isFresh?quote:null,quote_at:quote?.at||null,
        quote_age_seconds:quote?ageSeconds(quote.at,now):null,
        history:samples.map(x=>({at:x.at,mid:x.mid,spread_bps:x.spread_bps}))};
    });
    const authorization=auth[0]||null;
    const traderAge=ageSeconds(last.observed_at,now),brainAge=ageSeconds(research?.finished_at||research?.started_at,now);
    const health={trader:traderAge===null?"UNKNOWN":traderAge<=480?"FRESH":"STALE",
      brain:brainAge===null?"UNKNOWN":brainAge<=1200?"FRESH":"STALE",
      trader_age_seconds:traderAge,brain_age_seconds:brainAge,
      execution_mode:last.mode,trade_status:last.status,
      research_status:research?.status||"UNKNOWN",
      broker_data_quality:research?.markets_checked?.[0]?.reason||null};
    const events=[];
    for(const f of cleanFills.slice(0,6))events.push({
      at:f.closed_at,type:"BROKER_CLOSED",symbol:f.symbol,
      label:"إغلاق صفقة مؤكد من سجل الوسيط",detail:f.side+" · "+f.family,
      net:f.net,currency:f.currency});
    for(const i of intents.slice(0,6))events.push({
      at:i.updated_at,type:"ORDER_JOURNAL",symbol:i.symbol,
      label:"تحديث سجل الأمر",detail:i.status+" · "+i.family});
    events.push({at:last.observed_at,type:"TRADER_SCAN",label:"فحص أسواق Fusion Demo",
      detail:last.status+" · "+last.mode});
    if(research?.finished_at)events.push({at:research.finished_at,type:"BRAIN_CYCLE",
      label:"دورة تحليل العقل",detail:research.status+" · "+(research.totals?.candidates??0)+" candidates"});
    events.sort((a,b)=>Date.parse(b.at)-Date.parse(a.at));
    const edgeLatest=new Map();
    for(const run of edgeRuns){
      const symbol=String(run.symbol||"").slice(0,24);
      if(!symbol||edgeLatest.has(symbol))continue;
      const report=run.report||{};
      edgeLatest.set(symbol,{symbol,at:run.evaluated_at,
        version:String(run.version||"").slice(0,70),
        status:String(report.status||"UNKNOWN").slice(0,70),
        source:"BROKER_OHLC_RECENT_SPREAD_PROXY_NOT_HISTORICAL",
        broker_verified_edge:false,execution_enabled:false,
        bar_count:Number(report.bar_count)||0,
        reference_spread_p90:numeric(report.reference_spread_p90),
        families:(Array.isArray(report.families)?report.families:[]).slice(0,3).map(f=>({
          family:String(f.family||"").slice(0,60),
          status:String(f.status||"UNKNOWN").slice(0,60),
          validation_n:Number(f.validation?.trades)||0,
          validation_expectancy_r:numeric(f.validation?.expectancy_r),
          stressed_expectancy_r:numeric(f.validation_stressed?.expectancy_r),
          holdout_n:Number(f.holdout?.trades)||0,
          holdout_report_only:true,execution_enabled:false
        }))});
    }
    const result={ok:true,mode:"READ_ONLY_LIVE_SNAPSHOTS",
      generated_at:new Date(now).toISOString(),
      trader_at:last.observed_at,
      cadence_seconds:{trader:300,brain:900,ui:20},
      account:{last4:String(last.account_last4||"").slice(-4),type:"MT5 DEMO",
        provider:"TickerAll",broker:"Fusion Markets"},
      health,
      authorization:{enabled:authorization?.enabled===true,
        expires_at:authorization?.expires_at||null,
        risk_pct:numeric(authorization?.risk_pct)},
      trades:{intents:counts[0].order_intents,closed:counts[0].closed_fills,
        net_by_currency:[...sumByCurrency].map(([currency,net])=>({currency,net})),
        recent:cleanFills.slice(0,12),orders:intents.map(i=>({
          symbol:i.symbol,family:i.family,side:i.side,status:i.status,
          created_at:i.created_at,updated_at:i.updated_at,
          broker_ticket_recorded:i.broker_ticket_recorded}))},
      brain:{status:research?.status||"UNKNOWN",updated_at:research?.finished_at||null,
        forward_broker_feedback:research?.notes?.forward_broker_feedback?{
          source:"BROKER_VERIFIED_CLOSED_DEMO_ONLY",
          closed:Number(research.notes.forward_broker_feedback.closed)||0,
          minimum_closed_for_review:Number(research.notes.forward_broker_feedback.minimum_closed_for_review)||30,
          auto_promotion:false,
          confidence:"INSUFFICIENT_FOR_PROMOTION",
          strategies:(Array.isArray(research.notes.forward_broker_feedback.strategies)?
            research.notes.forward_broker_feedback.strategies:[]).slice(0,8).map(x=>({
              symbol:String(x.symbol||"").slice(0,24),family:String(x.family||"").slice(0,70),
              closed:Number(x.closed)||0,winners:Number(x.winners)||0,
              booked_net:numeric(x.booked_net),currency:String(x.currency||"").slice(0,3)
            }))
        }:null,
        broker_selection:research?.notes?.broker_selection||null,
        forward_feedback:research?.notes?.forward_broker_feedback||null,
        candidates:counts[0].candidates,
        analyses:counts[0].verified_brain_runs,
        cycles_24h:counts[0].research_cycles_24h,
        trade_cycles_24h:counts[0].trade_cycles_24h,
        last_market:research?.markets_checked?.[0]||null,
        notes:research?.totals||null},
      scan_history:scanHistory.map(row=>({
        at:row.observed_at,status:String(row.status||"UNKNOWN").slice(0,60),
        mode:String(row.mode||"UNKNOWN").slice(0,60),
        orders_sent:Number(row.orders_sent)||0,
        signals:Array.isArray(row.observations)?row.observations.filter(x=>x?.side&&x?.strategy).length:0,
        blocked:Array.isArray(row.observations)?row.observations.filter(x=>x?.status&&x.status!=="NO_VALID_CLOSED_BAR_SIGNAL").length:0
      })),
      research_history:researchHistory.map(row=>({
        at:row.finished_at||row.started_at,status:String(row.status||"UNKNOWN").slice(0,60),
        candidates:Number(row.totals?.candidates)||0,
        symbol:String(row.markets_checked?.[0]?.symbol||"").slice(0,24),
        reason:String(row.markets_checked?.[0]?.reason||"").slice(0,90),
        hypotheses:Number(row.markets_checked?.[0]?.hypotheses)||0
      })),
      amt_curriculum:{
        ...amtCurriculum.curriculumStatus(),
        sources:amtCurriculum.SOURCE_CATALOG.map(x=>({
          id:x.id,order:x.order,url:x.url,content_status:x.content_status,
          transcript_verified:x.transcript_verified,captions_indexed:x.captions_indexed,
          evidence_anchors:x.evidence_anchors
        }))
      },
      pdf_curriculum:pdfCurriculum.status(),
      source_patterns:research?.notes?.edge_lab?.source_patterns||null,
      edge_lab:[...edgeLatest.values()],markets,events:events.slice(0,12)};
    return send(res,200,result);
  }catch(e){
    console.error("sentinel_live_api_error",String(e?.code||"READ_ERROR").slice(0,50));
    return send(res,503,{ok:false,error:"LIVE_TELEMETRY_TEMPORARILY_UNAVAILABLE"});
  }
};
