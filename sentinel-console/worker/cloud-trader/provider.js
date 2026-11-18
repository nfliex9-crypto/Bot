"use strict";
// Uses the encrypted API key already stored for the Sentinel TickerAll integration.
const BASE="https://api.tickerall.com";
const ACCOUNT=/^[A-Za-z0-9_-]{3,128}$/;
const SYMBOL=/^[A-Za-z0-9._#-]{2,24}$/;
function provider(token,{fetcher=fetch,allowWrites=false,timeoutMs=12000}={}){
 if(typeof token!=="string"||token.length<12)throw Error("TICKERALL_TOKEN_MISSING");
 async function call(method,path,body,key){
  const route=path.split('?')[0];
  const okay=method==="GET"&&(route==="/v1/accounts"||/^\/v1\/accounts\/[A-Za-z0-9_-]{3,128}(?:\/(?:candles|orders|history|deals-history|symbols(?:\/[A-Za-z0-9._#-]{2,24}\/(?:spec|quote))?))?$/.test(route));
  const trade=method==="POST"&&/^\/v1\/accounts\/[A-Za-z0-9_-]{3,128}\/orders$/.test(route);
  if(!okay&&!trade)throw Error("PROVIDER_ROUTE_NOT_ALLOWED");
  if(trade&&(!allowWrites||!/^[a-f0-9]{64}$/.test(key||"")))throw Error("REMOTE_ORDERS_DISABLED");
  if(trade&&(body?.type!=="market"||!SYMBOL.test(body?.symbol||"")||!["BUY","SELL"].includes(body?.side)||!(body.volume>0)||!(body.stopLoss>0)||!(body.takeProfit>0)||typeof body.comment!=="string"||body.comment.length>31))throw Error("UNSAFE_ORDER_BODY");
  const url=new URL(path,BASE);if(url.origin!==BASE)throw Error("PROVIDER_ORIGIN_NOT_ALLOWED");
  const h={Authorization:"Bearer "+token,Accept:"application/json"};if(trade){h["Content-Type"]="application/json";h["Idempotency-Key"]=key}
  const r=await fetcher(url.toString(),{method,headers:h,body:trade?JSON.stringify(body):undefined,redirect:"error",cache:"no-store",signal:AbortSignal.timeout(route.endsWith("/candles")?Math.max(timeoutMs,20000):timeoutMs)});
  if(!r.ok){let code="HTTP_"+r.status;try{code=String((await r.json())?.error||code).slice(0,80)}catch(_){}throw Error("TICKERALL_"+code)}
  return await r.json();
 }
 return {
  accounts:()=>call("GET","/v1/accounts"),
  account:id=>{if(!ACCOUNT.test(id))throw Error("INVALID_ACCOUNT_ID");return call("GET","/v1/accounts/"+id)},
  symbols:id=>{if(!ACCOUNT.test(id))throw Error("INVALID_ACCOUNT_ID");return call("GET","/v1/accounts/"+id+"/symbols")},
  quote:(id,s)=>{if(!ACCOUNT.test(id)||!SYMBOL.test(s))throw Error("INVALID_ID_OR_SYMBOL");return call("GET",`/v1/accounts/${id}/symbols/${s}/quote`)},
  spec:(id,s)=>{if(!ACCOUNT.test(id)||!SYMBOL.test(s))throw Error("INVALID_ID_OR_SYMBOL");return call("GET",`/v1/accounts/${id}/symbols/${s}/spec`)},
  candles:(id,s,tf,hours)=>{if(!ACCOUNT.test(id)||!SYMBOL.test(s)||!["M15","H1"].includes(tf)||!Number.isInteger(hours)||hours<24||hours>400)throw Error("INVALID_CANDLE_REQUEST");return call("GET",`/v1/accounts/${id}/candles?symbol=${encodeURIComponent(s)}&timeframe=${tf}&hours=${hours}`)},
  orders:id=>{if(!ACCOUNT.test(id))throw Error("INVALID_ACCOUNT_ID");return call("GET",`/v1/accounts/${id}/orders`)},
  history:id=>{if(!ACCOUNT.test(id))throw Error("INVALID_ACCOUNT_ID");return call("GET",`/v1/accounts/${id}/history`)},
  submit:(id,request,key)=>{if(!ACCOUNT.test(id))throw Error("INVALID_ACCOUNT_ID");return call("POST",`/v1/accounts/${id}/orders`,request,key)}
 };
}
module.exports={provider};
