"use strict";
/**
 * Broker-grade research ingestion contracts.
 * Account readiness != price history readiness; no fabricated spread or fills.
 * Supports TickerAll's documented Unix-second candle timestamps and native symbols.
 */
const {normalizeCandles}=require("./engine.js");
const TF_MS={M15:900000,H1:3600000};
const LOOKBACK_HOURS={M15:1440,H1:3000};
const PRIORITY=[
  {name:"gold",re:/^(?:XAUUSD|GOLD)(?:[._#-]?[A-Za-z0-9]+)?$/i},
  {name:"btc",re:/^BTCUSD(?:[._#-]?[A-Za-z0-9]+)?$/i},
  {name:"forex",re:/^EURUSD(?:[._#-]?[A-Za-z0-9]+)?$/i},
  {name:"nas",re:/^(?:NAS100|US100|USTEC)(?:[._#-]?[A-Za-z0-9]+)?$/i}
];
const symbolOK=s=>typeof s==="string"&&/^[A-Za-z0-9._#-]{2,24}$/.test(s);
function selectMarkets(payload,now=new Date()){
 const catalog=(Array.isArray(payload)?payload:payload?.symbols||[])
   .map(x=>typeof x==="string"?x:x?.symbol).filter(symbolOK);
 const weekend=[0,6].includes(now.getUTCDay());
 return PRIORITY.filter(x=>!weekend||x.name==="btc")
  .map(x=>catalog.find(s=>x.re.test(s))).filter(Boolean).slice(0,4);
}
function selectJob(symbols,previous,now=new Date(),minRefreshMs=2*3600000){
 const records=Array.isArray(previous)?previous:[];
 const jobs=selectableJobs(symbols);
 const unique=new Map(records.map(r=>[String(r.symbol)+"|"+String(r.timeframe),{
   last:new Date(r.attempted_at??r.imported_at).getTime(),
   status:String(r.status||"UNKNOWN")
 }]));
 return jobs.map((x,i)=>{
  const prior=unique.get(x.symbol+"|"+x.timeframe);
  return {...x,index:i,last:prior?.last??0,status:prior?.status??"NEVER"};
 }).filter(x=>!x.last||!Number.isFinite(x.last)||
    now.getTime()-x.last>=(["ERROR","NO_CLOSED_BROKER_CANDLES"].includes(x.status)?30*60000:minRefreshMs))
 .sort((a,b)=>(a.last-b.last)||(a.index-b.index))[0]||null;
}
function selectableJobs(symbols){
 return symbols.flatMap(symbol=>["M15","H1"].map(timeframe=>({symbol,timeframe,hours:LOOKBACK_HOURS[timeframe]})));
}
function normalizeBatch(payload,{timeframe,now=new Date()}={}){
 if(!Object.hasOwn(TF_MS,timeframe))throw Error("INVALID_BROKER_TIMEFRAME");
 const input=Array.isArray(payload?.candles)?payload.candles:[];
 const interval=TF_MS[timeframe],closed=[];
 let openBarExcluded=0,futureRejected=0;
 for(const x of input.slice(-10000)){
  const t=x?.timestamp;
  const parsed=typeof t==="number"&&Number.isFinite(t)?(t<1e11?t*1000:t):Date.parse(String(t||""));
  if(!Number.isSafeInteger(parsed)){futureRejected++;continue}
  if(parsed>now.getTime()||parsed<Date.UTC(1990,0,1)){futureRejected++;continue}
  if(parsed+interval>now.getTime()){openBarExcluded++;continue}
  closed.push(x);
 }
 const n=normalizeCandles(closed);
 const coverage=String(payload?.coverage||"unknown");
 const truncated=payload?.truncated===true||input.length>10000;
 const quality={
  ...n.quality,raw_provider_rows:input.length,
  closed_rows:n.bars.length,open_bar_excluded:openBarExcluded,
  bad_timestamps:futureRejected,provider_coverage:coverage,
  truncated,spread_verified_rows:n.bars.filter(b=>b.spread!==null&&b.spread>0).length
 };
 return {
  bars:n.bars,
  quality,
  coverage,
  truncated,
  safeForResearch:n.bars.length>=900&&coverage==="complete"&&!truncated&&
   quality.rejected_rows===0&&quality.duplicate_rows===0&&futureRejected===0&&
   quality.missing_spread_ratio<=.25,
  accepted:n.bars.length
 };
}
module.exports={selectMarkets,selectJob,selectableJobs,normalizeBatch,LOOKBACK_HOURS};
