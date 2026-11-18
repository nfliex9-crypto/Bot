"use strict";
const {neon}=require("@neondatabase/serverless");
function reply(res,status,body){
 res.setHeader("Cache-Control","private,no-store");
 res.setHeader("X-Content-Type-Options","nosniff");
 res.setHeader("Cross-Origin-Resource-Policy","same-origin");
 return res.status(status).json(body);
}
function protectedOwner(req){
 if(process.env.SENTINEL_VERCEL_SSO!=="enabled")return false;
 const host=String(req.headers.host||"").toLowerCase();
 return /^sentinel-mt5-console(?:-[a-z0-9-]+)?\.vercel\.app$/.test(host);
}
module.exports=async(req,res)=>{
 if(req.method!=="GET")return reply(res,405,{ok:false,error:"READ_ONLY_ENDPOINT"});
 if(!protectedOwner(req))return reply(res,403,{ok:false,error:"PROTECTED_DASHBOARD_REQUIRED"});
 if(!process.env.DATABASE_URL)return reply(res,503,{ok:false,error:"DATABASE_NOT_CONFIGURED"});
 const sql=neon(process.env.DATABASE_URL);
 try{
  const [workers,cycles,candidates,papers,stats,publicResearch,marketImports,brokerBars,brokerHypotheses,spreadObservations]=await Promise.all([
   sql`SELECT status,last_heartbeat_at,last_success_at,last_cycle_id,last_error FROM sentinel_autonomy_worker_state WHERE worker_name='sentinel-autonomy' LIMIT 1`,
   sql`SELECT cycle_id,started_at,finished_at,status,account_id,totals,notes,markets_checked FROM sentinel_autonomy_cycles ORDER BY started_at DESC LIMIT 8`,
   sql`SELECT candidate_id,symbol,timeframe,family,status,reward_points,evaluated_cycles,metrics,last_evaluated_at FROM sentinel_autonomy_candidates ORDER BY last_evaluated_at DESC,reward_points DESC LIMIT 60`,
   sql`SELECT doi,title,published_year,topic,source_url,source_kind,first_seen_at FROM sentinel_autonomy_papers ORDER BY last_seen_at DESC LIMIT 16`,
   sql`SELECT status,COUNT(*)::int AS count FROM sentinel_autonomy_candidates GROUP BY status`,
   sql`SELECT provider,symbol,timeframe,candle_count,created_at,analysis->>'disclaimer' AS disclaimer
     FROM sentinel_autonomy_public_hypotheses ORDER BY created_at DESC LIMIT 3`,
   sql`SELECT symbol,timeframe,status,provider_rows,stored_rows,coverage,missing_spread_ratio,
       open_bar_excluded,error_code,attempted_at,last_success_at
       FROM sentinel_autonomy_import_attempts ORDER BY attempted_at DESC LIMIT 16`,
   sql`SELECT symbol,timeframe,COUNT(*)::int AS candle_count,
       COUNT(spread)::int AS candles_with_spread,MAX(bar_time) AS newest_closed_bar
       FROM sentinel_brain_candles GROUP BY symbol,timeframe ORDER BY symbol,timeframe LIMIT 24`,
   sql`SELECT symbol,timeframe,candle_count,missing_spread_ratio,
       jsonb_array_length(analysis->'hypotheses')::int AS idea_count,
       generated_at FROM sentinel_autonomy_broker_hypotheses
       ORDER BY generated_at DESC LIMIT 12`,
   sql`SELECT symbol,COUNT(*)::int AS observations,
       ROUND((PERCENTILE_CONT(0.90) WITHIN GROUP
         (ORDER BY (10000*(ask-bid)/NULLIF((ask+bid)/2,0))::double precision))::numeric,2)
         AS p90_spread_bps,
       MAX(observed_at) AS latest_observed_at
       FROM sentinel_autonomy_spread_observations
       GROUP BY symbol ORDER BY symbol LIMIT 20`
  ]);
  const w=workers[0]||null;
  const last=w?.last_heartbeat_at?new Date(w.last_heartbeat_at).getTime():0;
  const heartbeatFresh=Number.isFinite(last)&&Date.now()-last<35*60000&&last<=Date.now()+60000;
  const worker={
   status:w?(heartbeatFresh?w.status:"STALE"):"NOT_DEPLOYED",
   last_heartbeat_at:w?.last_heartbeat_at||null,
   last_success_at:w?.last_success_at||null,
   last_error:w?.last_error||null,
   fresh:heartbeatFresh
  };
  return reply(res,200,{ok:true,mode:"AUTONOMOUS_RESEARCH_ONLY",worker,
   cycles,stats,public_research:publicResearch,market_imports:marketImports,broker_candles:brokerBars,broker_hypotheses:brokerHypotheses,spread_observations:spreadObservations,
   candidates:candidates.map(c=>({
    id:c.candidate_id,symbol:c.symbol,timeframe:c.timeframe,family:c.family,
    status:c.status,reward_points:c.reward_points,evaluated_cycles:c.evaluated_cycles,
    last_evaluated_at:c.last_evaluated_at,
    validation:c.metrics?.validation,holdout:c.metrics?.holdout,
    robustness:c.metrics?.robustness,dataset:c.metrics?.dataset?.id
   })),
   papers:papers.map(p=>({title:p.title,year:p.published_year,doi:p.doi,
    topic:p.topic,url:p.source_url,source_kind:p.source_kind})),
   generated_at:new Date().toISOString(),orders_enabled:false,
   capital_multiplier:1});
 }catch(e){
  console.error("sentinel_autonomy_api_failure",String(e?.code||"DATABASE_QUERY_FAILED").slice(0,80));
  return reply(res,503,{ok:false,error:"AUTONOMY_DATA_NOT_AVAILABLE"});
 }
};
