"use strict";
/**
 * Immutable, content-addressed market research inputs.
 * Qlib-style reproducibility, OpenBB-style data provenance, LEAN-like
 * deterministic event replay. No data sources or paid APIs are installed.
 */
const {createHash}=require("node:crypto");
function numberToken(value){
 if(value===null||value===undefined)return "null";
 if(typeof value!=="number"||!Number.isFinite(value))
  throw Error("NON_FINITE_CANDLE_VALUE");
 return Object.is(value,-0)?"0":String(value);
}
function canonicalBars(bars){
 if(!Array.isArray(bars))throw Error("BARS_EXPECTED");
 let prior=-Infinity;
 return bars.map((b,i)=>{
  const ts=Number(b.timestamp);
  if(!Number.isSafeInteger(ts)||ts<=prior)throw Error("BARS_NOT_STRICTLY_INCREASING");
  prior=ts;
  return [
   ts,
   numberToken(b.open),
   numberToken(b.high),
   numberToken(b.low),
   numberToken(b.close),
   numberToken(b.spread),
   numberToken(b.tickVolume??null)
  ].join("|");
 }).join("\n");
}
function fingerprint(bars,{symbol,timeframe,coverage="unknown",provider="TickerAll MT5 Demo"}={}){
 const sym=String(symbol||"UNKNOWN").toUpperCase().slice(0,28);
 const tf=String(timeframe||"UNKNOWN").toUpperCase().slice(0,12);
 const source=String(provider||"unknown").slice(0,80);
 const payload=["SENTINEL-DATA-V1",source,sym,tf,String(coverage),canonicalBars(bars)].join("\n");
 const hash=createHash("sha256").update(payload,"utf8").digest("hex");
 return {
  id:hash,algorithm:"SHA-256",format:"sentinel-data-v1",provider:source,
  symbol:sym,timeframe:tf,coverage:String(coverage),rows:bars.length,
  first_bar_utc:bars.length?new Date(bars[0].timestamp).toISOString():null,
  last_bar_utc:bars.length?new Date(bars[bars.length-1].timestamp).toISOString():null
 };
}
module.exports={fingerprint,canonicalBars};
