"use strict";
/**
 * Research-only L2 snapshot diagnostics. Never emits orders, trade sides or
 * executable signals. A quote-based CFD book is not a centralized exchange.
 * Requires a source-specific collector and real sequence-checked snapshots.
 */
const SOURCES=new Set(["MT5_BROKER_DOM","BINANCE_SPOT_DEPTH","CME_GC_FUTURES"]);
const finite=x=>typeof x==="number"&&Number.isFinite(x);
function levels(rows,side){
 if(!Array.isArray(rows)||rows.length<1||rows.length>1000)return null;
 const parsed=rows.map(level=>{
  const price=Array.isArray(level)?Number(level[0]):Number(level?.price);
  const size=Array.isArray(level)?Number(level[1]):Number(level?.size);
  return {price,size};
 });
 if(parsed.some(x=>!finite(x.price)||!finite(x.size)||x.price<=0||x.size<=0))return null;
 parsed.sort((a,b)=>side==="bid"?b.price-a.price:a.price-b.price);
 if(parsed.some((x,i)=>i>0&&x.price===parsed[i-1].price))return null;
 return parsed;
}
function inspect(snapshot,{now=Date.now(),maxAgeMs=1500,depth=5}={}){
 const blocked=reason=>({status:"UNUSABLE",reason,orders_enabled:false,execution_signal:null});
 if(!snapshot||!SOURCES.has(snapshot.source))return blocked("UNKNOWN_BOOK_SOURCE");
 const time=typeof snapshot.timestamp==="number"?snapshot.timestamp:Date.parse(String(snapshot.timestamp||""));
 if(!Number.isFinite(time)||time>now+100||now-time>maxAgeMs)return blocked("BOOK_STALE_OR_FUTURE");
 if(!Number.isInteger(depth)||depth<1||depth>20)return blocked("INVALID_DEPTH");
 const bids=levels(snapshot.bids,"bid"),asks=levels(snapshot.asks,"ask");
 if(!bids||!asks)return blocked("INVALID_BOOK_LEVELS");
 const bid=bids[0].price,ask=asks[0].price;
 if(bid>=ask)return blocked("CROSSED_OR_LOCKED_BOOK");
 const n=Math.min(depth,bids.length,asks.length);
 const buy=bids.slice(0,n).reduce((s,x)=>s+x.size,0);
 const sell=asks.slice(0,n).reduce((s,x)=>s+x.size,0);
 const spread=ask-bid,mid=(bid+ask)/2;
 return {
  status:"RESEARCH_ONLY",source:snapshot.source,symbol:String(snapshot.symbol||"").slice(0,24),
  timestamp:new Date(time).toISOString(),levels_used:n,
  best_bid:bid,best_ask:ask,spread,spread_bps:spread/mid*10000,
  bid_size:buy,ask_size:sell,
  imbalance:(buy-sell)/(buy+sell),
  microprice:(ask*bids[0].size+bid*asks[0].size)/(bids[0].size+asks[0].size),
  caveat:snapshot.source==="MT5_BROKER_DOM"?"BROKER_SPECIFIC_CFD_LIQUIDITY":
   snapshot.source==="CME_GC_FUTURES"?"FUTURES_NOT_XAUUSD_CFD":"VENUE_SPECIFIC_SPOT_BOOK",
  orders_enabled:false,execution_signal:null
 };
}
function studyPersistence(snapshots,{now=Date.now(),minSamples=20,minSpanMs=2000,maxAgeMs=1500}={}){
 if(!Array.isArray(snapshots)||snapshots.length<minSamples)
  return {status:"INSUFFICIENT_SNAPSHOTS",orders_enabled:false,execution_signal:null};
 const ordered=snapshots.map(s=>inspect(s,{now,maxAgeMs:Math.max(60000,maxAgeMs)}));
 if(ordered.some(x=>x.status!=="RESEARCH_ONLY"))return {status:"BAD_SNAPSHOT",orders_enabled:false,execution_signal:null};
 const recent=ordered.slice(-minSamples);
 const times=recent.map(x=>Date.parse(x.timestamp));
 if(times.some((x,i)=>i&&x<=times[i-1])||times.at(-1)>now+100||
    now-times.at(-1)>maxAgeMs||times.at(-1)-times[0]<minSpanMs||
    recent.some(x=>x.source!==recent[0].source||x.symbol!==recent[0].symbol))
  return {status:"INVALID_SEQUENCE_OR_STALE",orders_enabled:false,execution_signal:null};
 const mean=recent.reduce((sum,x)=>sum+x.imbalance,0)/recent.length;
 const signConsistency=recent.filter(x=>Math.sign(x.imbalance)===Math.sign(mean)).length/recent.length;
 return {status:"PERSISTENCE_OBSERVED_NOT_PROVEN",source:recent[0].source,
  symbol:recent[0].symbol,samples:recent.length,mean_imbalance:mean,
  sign_consistency:signConsistency,orders_enabled:false,execution_signal:null,
  note:"Visible resting liquidity can cancel or spoof; do not infer aggressive trades or predict fills."};
}
module.exports={inspect,studyPersistence};
