"use strict";
// Pure, deterministic MT5 DEMO signals and preflight. No credentials or HTTP here.
const crypto=require("node:crypto");
const sourceSignals=require("./source-signals.js");
const orderflow=require("../orderflow/delta-engine.js");
const deltaCurriculum=require("../../brain/orderflows-delta-curriculum.js");
const FAMILIES=new Set(["trend_pullback","donchian_breakout",...Object.keys(sourceSignals.RULES)]);
function finite(v){return typeof v==="number"&&Number.isFinite(v)?v:null}
function asUTC(v){if(typeof v==="number")return v<1e11?v*1000:v;const t=Date.parse(String(v||""));return Number.isFinite(t)?t:NaN}
function parseCandles(raw,tf,now=Date.now()){
 if(!Array.isArray(raw))throw Error("CANDLES_NOT_ARRAY");
 const length=tf==="M15"?900000:tf==="H1"?3600000:NaN;
 if(!Number.isFinite(length))throw Error("INVALID_TIMEFRAME");
 let prev=-Infinity;
 const closed=[];
 for(const b of raw){
  const time=asUTC(b.timestamp??b.time),open=Number(b.open),high=Number(b.high),low=Number(b.low),close=Number(b.close);
  if(!Number.isSafeInteger(time)||time<=prev||![open,high,low,close].every(Number.isFinite)||low<=0||high<Math.max(open,close)||low>Math.min(open,close))throw Error("INVALID_OR_NONMONOTONIC_BARS");
  prev=time;
  if(time+length<=now)closed.push({time,open,high,low,close});
 }
 return closed;
}
function ema(values,length){if(values.length<length)throw Error("INSUFFICIENT_EMA");let x=values.slice(0,length).reduce((a,b)=>a+b,0)/length;const k=2/(length+1);for(const v of values.slice(length))x+=k*(v-x);return x}
function atr(bars){if(bars.length<16)throw Error("INSUFFICIENT_ATR");const tr=[];for(let i=1;i<bars.length;i++){const b=bars[i],p=bars[i-1];tr.push(Math.max(b.high-b.low,Math.abs(b.high-p.close),Math.abs(b.low-p.close)))}return tr.slice(-14).reduce((a,b)=>a+b,0)/14}
function decide(symbol,m15,h1,now=Date.now(),strategyMode="baseline",weeklyPriorities={}){
 if(!["baseline","source_only","source_first"].includes(strategyMode))throw Error("INVALID_STRATEGY_MODE");
 if(strategyMode!=="baseline"){
  const source=sourceSignals.researchSignal(symbol,m15,h1,now,weeklyPriorities);
  if(source||strategyMode==="source_only")return source;
 }
 if(m15.length<110||h1.length<90)return null;
 if(now-(m15.at(-1).time+900000)>16*60000||now-(h1.at(-1).time+3600000)>4*3600000)return null;
 const m=m15.map(b=>b.close),h=h1.map(b=>b.close),fast=ema(m,20),slow=ema(m,50),hfast=ema(h,20),hslow=ema(h,50),a=atr(m15);
 if(!(a>0))return null;
 const side=fast>slow&&hfast>hslow?1:fast<slow&&hfast<hslow?-1:0;
 if(!side)return null;
 const priorFast=ema(m.slice(0,-1),20),prev=m15.at(-2),last=m15.at(-1);
 let family=null;
 if(side===1&&prev.close<=priorFast&&last.close>fast||side===-1&&prev.close>=priorFast&&last.close<fast)family="trend_pullback";
 else{
  const history=m15.slice(-21,-1);
  if(side===1&&last.close>Math.max(...history.map(x=>x.high))||side===-1&&last.close<Math.min(...history.map(x=>x.low)))family="donchian_breakout";
 }
 if(!family)return null;
 return {symbol,family,side,bar_time:last.time,reference_close:last.close,atr:a,stop_atr:1.5,reward_r:2};
}
function keyFor(accountId,signal){return crypto.createHash("sha256").update(["SENTINEL_CLOUD_V1",accountId,signal.symbol,signal.family,signal.side,signal.bar_time].join("|")).digest("hex")}
function selectAccount(accounts,explicitId,preferredId){
 const matches=(Array.isArray(accounts)?accounts:accounts?.accounts||[]).filter(a=>a?.broker==="mt5"&&a.isDemo===true&&a.hot===true&&a.readOnly!==true);
 if(explicitId){const a=matches.find(x=>x.id===explicitId);return a?{account:a,status:"DEMO_SELECTED"}:{account:null,status:"AUTHORIZED_DEMO_NOT_HOT"}}
 if(preferredId){const a=matches.find(x=>x.id===preferredId);if(a)return {account:a,status:"EXISTING_SENTINEL_DEMO_SELECTED"}}
 return matches.length===1?{account:matches[0],status:"ONLY_HOT_DEMO_SELECTED"}:{account:null,status:matches.length?"MULTIPLE_DEMOS_AMBIGUOUS":"NO_HOT_MT5_DEMO"};
}
function floorVolume(raw,spec,maxLots=.5){
 const min=finite(spec.volumeMin),max=finite(spec.volumeMax),step=finite(spec.volumeStep);
 if(min===null||max===null||step===null||min<=0||max<min||step<=0||!Number.isFinite(raw)||raw<min)return 0;
 const ceiling=Math.min(maxLots,max,raw);const count=Math.floor((ceiling-min)/step+1e-9);
 return Number((min+count*step).toFixed(8));
}
function preflight({signal,quote,spec,equity,accountCurrency=null,riskPct=.25,maxSpreadBps=25,maxLots=.5,now=Date.now()}){
 if(!signal||!FAMILIES.has(signal.family)||![-1,1].includes(signal.side)||!Number.isSafeInteger(signal.bar_time)||now-signal.bar_time-900000<0||now-signal.bar_time-900000>900000)return {ok:false,reason:"SIGNAL_NOT_FRESH_OR_ALLOWED"};
 const bid=finite(quote?.bid),ask=finite(quote?.ask),point=finite(spec?.point),tickSize=finite(spec?.tickSize),value=finite(spec?.tickValueAccount),digits=spec?.digits;
 if(bid===null||ask===null||bid<=0||ask<=bid)return {ok:false,reason:"QUOTE_UNAVAILABLE"};
 if(!Number.isInteger(digits)||digits<0||digits>10||point===null||point<=0||tickSize===null||tickSize<=0||value===null||value<=0||spec?.specSource!=="broker"||!['wire','override'].includes(spec.tickValueCurrency?.source)||spec.tickValueCurrency?.code===undefined)return {ok:false,reason:"NATIVE_ACCOUNT_TICK_VALUE_UNVERIFIED"};
 if(finite(equity)===null||equity<=0||riskPct<=0||riskPct>.5)return {ok:false,reason:"EQUITY_OR_RISK_UNAVAILABLE"};
 if(accountCurrency!==null){
  const verified=verifyContract(spec,accountCurrency);
  if(!verified.ok)return verified;
 }
 const spread=(ask-bid)/((ask+bid)/2)*10000;if(spread>maxSpreadBps)return {ok:false,reason:"SPREAD_TOO_WIDE"};
 if(!Number.isFinite(signal.reference_close)||signal.reference_close<=0||
    Math.abs((ask+bid)/2-signal.reference_close)>3*signal.atr+(ask-bid))
   return {ok:false,reason:"PRICE_DIVERGED_FROM_CLOSED_BAR"};
 const entry=signal.side===1?ask:bid,minimumStop=(finite(spec.stopLevel)??NaN)*point;
 if(!Number.isFinite(minimumStop)||minimumStop<0||!Number.isFinite(signal.atr)||signal.atr<=0)return {ok:false,reason:"STOP_LEVEL_UNAVAILABLE"};
 const distance=Math.ceil(Math.max(signal.atr*signal.stop_atr,minimumStop*1.5+ask-bid)/tickSize)*tickSize;
 const round=v=>Number(v.toFixed(digits));const sl=round(entry-signal.side*distance),tp=round(entry+signal.side*distance*signal.reward_r);
 const trigger=signal.side===1?bid:ask;
 if(signal.side===1&&!(sl<trigger-minimumStop&&tp>trigger+minimumStop)||signal.side===-1&&!(sl>trigger+minimumStop&&tp<trigger-minimumStop))return {ok:false,reason:"STOP_LEVEL_CONFLICT"};
 const perLot=distance/tickSize*value;const raw=(equity*riskPct/100)/perLot;const volume=floorVolume(raw,spec,maxLots);
 if(!(volume>0)||volume*perLot>equity*riskPct/100*1.000001)return {ok:false,reason:"RISK_BELOW_MIN_VOLUME"};
 return {ok:true,request:{type:"market",symbol:signal.symbol,side:signal.side===1?"BUY":"SELL",volume,stopLoss:sl,takeProfit:tp},risk:volume*perLot,spread_bps:spread};
}
function authorizedFusionDemo(row,account,now=Date.now()){
 const expiry=Date.parse(String(row?.expires_at||""));
 const risk=Number(row?.risk_pct);
 return Boolean(row?.enabled===true&&row.account_id===account?.id&&
  /^[0-9]{4}$/.test(String(row.expected_last4||""))&&
  String(account.accountNumber||"").endsWith(String(row.expected_last4))&&
  /fusion/i.test(String(account.server||""))&&
  String(row.expected_server||"").toLowerCase()===String(account.server||"").toLowerCase()&&
  account.broker==="mt5"&&account.isDemo===true&&account.hot===true&&
  account.readOnly!==true&&Number.isFinite(expiry)&&expiry>now&&
  Number.isFinite(risk)&&risk>0&&risk<=0.25);
}
function verifyContract(spec,accountCurrency){
 const val=finite(spec?.tickValueAccount),size=finite(spec?.tickSize);
 const min=finite(spec?.volumeMin),step=finite(spec?.volumeStep),max=finite(spec?.volumeMax);
 if(spec?.specSource!=="broker"||size===null||size<=0||
    val===null||val<=0||min===null||min<=0||step===null||step<=0||
    max===null||max<min)return {ok:false,reason:"BROKER_CONTRACT_VALUE_UNKNOWN"};
 if(!/^[A-Z]{3}$/.test(String(accountCurrency||""))||
    !["wire","override"].includes(spec?.tickValueCurrency?.source)||
    spec?.tickValueCurrency?.code!==accountCurrency)
    return {ok:false,reason:"ACCOUNT_CURRENCY_TICK_VALUE_UNVERIFIED"};
 return {ok:true,reason:"BROKER_CONTRACT_VERIFIED"};
}
function demoExecutionAllowed(env,account){
 return env.SENTINEL_CLOUD_MODE==="demo_execution"&&env.SENTINEL_CLOUD_ENABLE_DEMO==="YES_I_AUTHORIZE_SENTINEL_DEMO_ONLY"&&env.SENTINEL_CLOUD_UNVERIFIED_TRIAL==="YES_EXPLICIT_DEMO_TRIAL"&&typeof env.SENTINEL_CLOUD_ACCOUNT_ID==="string"&&env.SENTINEL_CLOUD_ACCOUNT_ID===account?.id&&account.isDemo===true&&account.hot===true&&account.broker==="mt5";
}

// Explicit source-verified executed-trade research path. Not wired to order submission.
function analyzeOrderflowTape(trades,feedOptions={},researchParams={},now=Date.now()){
 if(!Array.isArray(trades)||!trades.length)return {status:"DATA_BLOCKED",reason:"NO_VERIFIED_EXECUTED_TRADE_TAPE",signals:[],executionEnabled:false};
 try{
  const bars=orderflow.buildBars(trades,{...feedOptions,now});
  const result=orderflow.evaluate(bars,researchParams,now);
  return {...result,course:deltaCurriculum.SOURCE,barCount:bars.length,executionEnabled:false};
 }catch(e){return {status:"DATA_BLOCKED",reason:String(e.message||e).slice(0,120),signals:[],executionEnabled:false};}
}
module.exports={analyzeOrderflowTape,deltaCurriculum,parseCandles,ema,atr,decide,keyFor,selectAccount,floorVolume,preflight,demoExecutionAllowed,authorizedFusionDemo,verifyContract};
