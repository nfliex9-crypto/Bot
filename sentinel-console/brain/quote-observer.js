"use strict";
/* Genuine MT5 demo bid/ask snapshots — research-only, no fake historical fills. */
function readQuote(raw,{accountId,symbol,now=new Date()}={}){
 if(typeof accountId!=="string"||!accountId||typeof symbol!=="string"||!symbol)
  throw Error("QUOTE_CONTEXT_REQUIRED");
 const bid=raw?.bid,ask=raw?.ask;
 if(typeof bid!=="number"||typeof ask!=="number"||
    !Number.isFinite(bid)||!Number.isFinite(ask)||bid<=0||ask<bid)
    return {status:"UNAVAILABLE",symbol,observed:false};
 const spread=ask-bid,mid=(ask+bid)/2;
 if(mid<=0)return {status:"UNAVAILABLE",symbol,observed:false};
 return {
  status:"OBSERVED",source:"TICKERALL_MT5_DEMO_QUOTE",
  symbol,bid,ask,spread,spread_bps:spread/mid*10000,
  at:now.toISOString(),observed:true
 };
}
async function recordQuote(sql,{accountId,symbol,raw,now=new Date()}={}){
 const q=readQuote(raw,{accountId,symbol,now});
 if(!q.observed)return q;
 await sql`INSERT INTO sentinel_autonomy_spread_observations
 (account_id,symbol,observed_at,bid,ask,spread,source)
 VALUES(${accountId},${symbol},${q.at},${q.bid},${q.ask},${q.spread},
 'TICKERALL_MT5_DEMO_QUOTE')
 ON CONFLICT(account_id,symbol,observed_at) DO NOTHING`;
 return {status:q.status,symbol:q.symbol,spread_bps:q.spread_bps,
    at:q.at,observed:true};
}
module.exports={readQuote,recordQuote};
