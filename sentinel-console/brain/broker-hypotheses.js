"use strict";
/* MT5 OHLC hypotheses with UNVERIFIED execution costs.
 * Does not override the broker-verification gate or create any orders.
 */
const {scoreFamily,seeds}=require("./strategy-factory.js");
const {fingerprint}=require("./provenance.js");
function proxyHypotheses(bars,{symbol,timeframe,coverage,missingSpreadRatio,datasetId}={}){
 if(!Array.isArray(bars)||bars.length<900||coverage!=="complete")
  return {status:"NOT_ELIGIBLE",hypotheses:[],reward_points:0,execution_enabled:false};
 // Explore only: 5 basis points of price as an assumed price-unit spread,
 // then the simulator doubles that spread under its stressed cost model.
 // These are neither broker quotes nor validated historical commission/slippage.
 const spreadAssumptionBps=5;
 const hypothetical=bars.map(bar=>({
  ...bar,spread:bar.spread!==null&&bar.spread>0?bar.spread:bar.close*spreadAssumptionBps/10000
 }));
 // Reproducible bounded challengers per immutable dataset. These NEVER earn
 // rewards when broker transaction-cost evidence is missing.
 const batchId=datasetId||fingerprint(bars,{symbol,timeframe,coverage}).id;
 const research=scoreFamily(hypothetical,{coverage:"complete",truncated:false,
  parents:seeds(),cycleId:batchId});
 return {
  status:"OHLC_HYPOTHESES_ONLY",
  symbol,timeframe,
  source:"MT5 broker OHLC with assumed unobserved spread",
  observed_spread_fraction:1-Number(missingSpreadRatio||0),
  assumed_spread_bps:spreadAssumptionBps,
  reward_points:0,execution_enabled:false,
  assumptions:{
   broker_spread_verified:false,commission_verified:false,slippage_verified:false,
   assumed_spread_bps:spreadAssumptionBps,double_cost_stress:true
  },
  hypotheses:research.candidates.map(x=>({
   id:x.id,family:x.family,
   status:"UNVERIFIED_BROKER_COST_HYPOTHESIS",
   validation:x.validation,holdout:x.holdout,
   robustness:x.robustness,
   reward_points:0,execution_enabled:false
  })),
  note:"Exploratory, simulated transaction costs: not a validated edge, not forward evidence, and never an execution signal."
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
