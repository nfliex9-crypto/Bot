"use strict";
/* Public BTCUSDT research only, no live account inference or order execution. */
const {normalizeCandles}=require("./engine.js");
const {fingerprint}=require("./provenance.js");
const {scoreFamily}=require("./strategy-factory.js");
const URL="https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=1000";
const PROVIDER="BINANCE_PUBLIC_SPOT";
function parseKlines(raw,now=new Date()){
 if(!Array.isArray(raw))throw Error("INVALID_PUBLIC_KLINES");
 const accepted=[];let invalid=0;
 for(const x of raw.slice(0,1000)){
  if(!Array.isArray(x)||x.length<8){invalid++;continue}
  const t=Number(x[0]),end=Number(x[6]),o=Number(x[1]),h=Number(x[2]),l=Number(x[3]),c=Number(x[4]),v=Number(x[5]);
  if(!Number.isSafeInteger(t)||!Number.isSafeInteger(end)||end<=t||end>=now.getTime()||
    ![o,h,l,c,v].every(Number.isFinite)||o<=0||l<=0||h<Math.max(o,c)||l>Math.min(o,c)){invalid++;continue}
  accepted.push({timestamp:t,open:o,high:h,low:l,close:c,spread:null,tickVolume:v});
 }
 const output=normalizeCandles(accepted);
 const gaps=output.bars.slice(1).filter((b,i)=>b.timestamp-output.bars[i].timestamp!==3600000).length;
 return {bars:output.bars,quality:{received:raw.length,accepted:output.bars.length,
  invalid:invalid+output.quality.rejected_rows,duplicates:output.quality.duplicate_rows,gaps,
  broker_spread_known:false}};
}
async function refreshPublic(sql,{fetcher,now=new Date()}={}){
 if(typeof fetcher!=="function")throw Error("FETCHER_REQUIRED");
 const last=await sql`SELECT MAX(created_at) AS last_run FROM sentinel_autonomy_public_hypotheses
 WHERE provider=${PROVIDER} AND symbol='BTCUSDT' AND timeframe='H1'`;
 if(last[0]?.last_run&&now.getTime()-new Date(last[0].last_run).getTime()<7200000)
  return {status:"NOT_DUE",source:PROVIDER};
 const raw=await fetcher(URL);
 const {bars,quality}=parseKlines(raw,now);
 if(bars.length<900||quality.invalid||quality.duplicates||quality.gaps)
  return {status:"DATA_QUALITY_REJECTED",source:PROVIDER,quality};
 const json=JSON.stringify(bars.map(b=>({t:new Date(b.timestamp).toISOString(),o:b.open,h:b.high,l:b.low,c:b.close,v:b.tickVolume})));
 await sql`INSERT INTO sentinel_autonomy_public_candles
 (provider,symbol,timeframe,bar_time,open,high,low,close,volume)
 SELECT ${PROVIDER},'BTCUSDT','H1',r.t,r.o,r.h,r.l,r.c,r.v FROM jsonb_to_recordset(${json}::jsonb)
 AS r(t timestamptz,o numeric,h numeric,l numeric,c numeric,v numeric)
 ON CONFLICT(provider,symbol,timeframe,bar_time) DO UPDATE SET
 open=EXCLUDED.open,high=EXCLUDED.high,low=EXCLUDED.low,close=EXCLUDED.close,
 volume=EXCLUDED.volume,fetched_at=NOW()`;
 const fp=fingerprint(bars,{provider:PROVIDER,symbol:"BTCUSDT",timeframe:"H1",coverage:"latest_1000_closed"});
 // Temporary spread proxy for sensitivity exploration only.
 // Always suppress strategy promotion and rewards on this non-broker source.
 const proxy=bars.map(b=>({...b,spread:b.close*.0006}));
 const research=scoreFamily(proxy,{coverage:"complete",truncated:false});
 const analysis={provider:PROVIDER,asset:"BTCUSDT",market:"spot_not_mt5",
  broker_verified:false,spread_observed:false,assumed_spread_fraction:.0006,
  data:fp,quality,
  hypotheses:research.candidates.map(c=>({id:c.id,family:c.family,
   validation:c.validation,holdout:c.holdout,robustness:c.robustness,
   status:"PUBLIC_HYPOTHESIS_REQUIRES_BROKER_CONFIRMATION",reward:0})),
  orders_enabled:false,disclaimer:"PUBLIC OHLC / ASSUMED COSTS: NOT BROKER EXECUTION EVIDENCE"};
 await sql`INSERT INTO sentinel_autonomy_public_hypotheses
 (dataset_id,provider,symbol,timeframe,candle_count,analysis)
 VALUES(${fp.id},${PROVIDER},'BTCUSDT','H1',${bars.length},${JSON.stringify(analysis)}::jsonb)
 ON CONFLICT(dataset_id) DO NOTHING`;
 return {status:"PUBLIC_HYPOTHESIS_ONLY",source:PROVIDER,
  candles:bars.length,hypotheses:analysis.hypotheses.length,
  dataset_id:fp.id,broker_verified:false,reward_points:0};
}
module.exports={URL,PROVIDER,parseKlines,refreshPublic};
