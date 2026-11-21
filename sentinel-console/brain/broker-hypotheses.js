"use strict";
/* MT5 OHLC gross-price research hypotheses.
 * Does not override the broker-verification gate or create any orders.
 */
const {scoreFamily,seeds}=require("./strategy-factory.js");
const {fingerprint}=require("./provenance.js");
function proxyHypotheses(bars,{symbol,timeframe,coverage,missingSpreadRatio,datasetId}={}){
 if(!Array.isArray(bars)||bars.length<900||coverage!=="complete")
  return {status:"NOT_ELIGIBLE",hypotheses:[],reward_points:0,execution_enabled:false};
 // Reproducible bounded challengers per immutable dataset. These NEVER earn
 // rewards when broker transaction-cost evidence is missing.
 const batchId=datasetId||fingerprint(bars,{symbol,timeframe,coverage}).id;
 const research=scoreFamily(bars,{coverage:"complete",truncated:false,
  parents:seeds(),cycleId:batchId});
 return {
  status:"OHLC_HYPOTHESES_ONLY",
  symbol,timeframe,
  source:"MT5 broker OHLC, gross price-only research",
  reward_points:0,execution_enabled:false,
  assumptions:{transaction_cost_model:"DISABLED",score_basis:"GROSS_PRICE_ONLY"},
  hypotheses:research.candidates.map(x=>({
   id:x.id,family:x.family,
   status:"GROSS_PRICE_HYPOTHESIS_UNVERIFIED",
   validation:x.validation,holdout:x.holdout,
   robustness:x.robustness,
   reward_points:0,execution_enabled:false
  })),
  note:"Gross price-only simulation. Not a validated forward edge or execution signal."
 };
}
async function recordBrokerHypotheses(sql,{account,symbol,timeframe,batch}){
 if(!batch?.bars?.length||batch.bars.length<900||batch.truncated||
    batch.coverage!=="complete"||batch.quality?.rejected_rows||batch.quality?.duplicate_rows)
  return {status:"NOT_ELIGIBLE",count:0};
 const report=proxyHypotheses(batch.bars,{symbol,timeframe,coverage:batch.coverage,
  missingSpreadRatio:batch.quality.missing_spread_ratio,
  datasetId:fingerprint(batch.bars,{symbol,timeframe,coverage:batch.coverage}).id});
 const identity=fingerprint(batch.bars,{
  provider:"TickerAll MT5 Demo native OHLC",
  symbol,timeframe,coverage:batch.coverage
 });
 await sql`INSERT INTO sentinel_autonomy_broker_hypotheses
 (dataset_id,account_id,symbol,timeframe,candle_count,missing_spread_ratio,assumptions,analysis,
  reward_points,execution_enabled)
 VALUES(${identity.id},${account},${symbol},${timeframe},${batch.bars.length},
   ${batch.quality.missing_spread_ratio},${JSON.stringify(report.assumptions)}::jsonb,
   ${JSON.stringify({...report,dataset:identity})}::jsonb,0,false)
 ON CONFLICT(dataset_id) DO NOTHING`;
 return {status:report.status,count:report.hypotheses.length,
  dataset_id:identity.id,reward_points:0,execution_enabled:false};
}
module.exports={proxyHypotheses,recordBrokerHypotheses};
