"use strict";
/** GROSS ZERO-DEDUCTION research replay. Never submits brokerage orders.
 * Input is an ordered JSON array of complete executed-trade-derived Delta bars.
 * Model price gaps at the next open; do not apply synthetic spread, fees or slippage.
 */
const fs=require("node:fs");
const composite=require("./composite-strategies.js");
const PAIRS=["sweep_divergence_bos","trend_delta_surge"];
const PARAMS=composite.PARAMS;
const DAY=86400000;
function date(x){return new Date(x).toISOString().slice(0,10)}
function atrAt(bars,i){
 if(i<14)return null;
 let a=0;
 for(let j=i-13;j<=i;j++){const b=bars[j],p=bars[j-1];a+=Math.max(b.high-b.low,Math.abs(b.high-p.close),Math.abs(b.low-p.close))}
 return a/14;
}
function run(bars,{trainDays=[],oosDays=[],holdingBars=12,stopATR=1.5,rewardR=2}={}){
 if(!Array.isArray(bars)||bars.length<100)throw Error("INSUFFICIENT_VERIFIED_BARS");
 if(![300000,900000].includes(bars[0].barMs))throw Error("UNSUPPORTED_BAR_SIZE");
 if(!bars.every((b,i)=>b.closed===true&&b.sourceQuality==="VERIFIED_AGGRESSOR_TRADES"&&
   b.venue==="BINANCE_SPOT"&&b.symbol==="BTCUSDT"&&
   b.barMs===bars[0].barMs&&Number.isFinite(b.delta)&&Number.isFinite(b.open)&&
   Number.isFinite(b.high)&&Number.isFinite(b.low)&&Number.isFinite(b.close)&&
   Number.isSafeInteger(b.openTime)&&
   (i===0||b.openTime>bars[i-1].openTime)))throw Error("UNVERIFIED_BARS");
 const train=new Set(trainDays),oos=new Set(oosDays),hourly=composite.hourlyBars(bars);
 const results={}, lastTaken={};
 for(const split of ["TRAIN","OOS"])for(const family of PAIRS){
  results[split+"|"+family]=[];lastTaken[split+"|"+family]=-1;
 }
 for(let i=100;i<bars.length-holdingBars-1;i++){
  const split=train.has(date(bars[i].openTime))?"TRAIN":oos.has(date(bars[i].openTime))?"OOS":null;
  if(!split||bars[i+1].openTime!==bars[i].closeTime)continue;
  const ar=atrAt(bars,i);
  if(!(ar>0))continue;
  const signals=composite.signalsAt(bars,i,hourly,PARAMS,bars[i].closeTime);
  for(const sig of signals){
   const key=split+"|"+sig.family;
   if(!(key in results)||i<=lastTaken[key])continue;
   const days=split==="TRAIN"?train:oos;
   const entryBar=bars[i+1];
   if(!days.has(date(entryBar.openTime)))continue;
   const entry=entryBar.open,risk=ar*stopATR,side=sig.side==="LONG"?1:-1;
   const stop=entry-side*risk,target=entry+side*risk*rewardR;
   let exited=false;
   for(let j=i+1;j<=Math.min(bars.length-1,i+holdingBars);j++){
    const b=bars[j],prev=bars[j-1];
    if(b.openTime!==prev.closeTime||!days.has(date(b.openTime)))break;
    const stopHit=side===1?b.low<=stop:b.high>=stop;
    const targetHit=side===1?b.high>=target:b.low<=target;
    let exit=null,reason="";
    if(stopHit){exit=side===1?Math.min(b.open,stop):Math.max(b.open,stop);reason=targetHit?"STOP_FIRST_BOTH":"STOP"}
    else if(targetHit){exit=target;reason="TARGET"}
    else if(j===i+holdingBars){exit=b.close;reason="TIME"}
    if(exit!==null){
     const grossR=side*(exit-entry)/risk;
     results[key].push({date:date(entryBar.openTime),signalTime:bars[i].closeTime,
      exitTime:b.closeTime,side:sig.side,entry,exit,stop,target,
      grossR,reason,signal:sig.detail});
     lastTaken[key]=j;exited=true;break;
    }
   }
  }
 }
 const metrics={};
 for(const [key,trades] of Object.entries(results)){
  const n=trades.length,rr=trades.map(x=>x.grossR),
    gains=rr.filter(x=>x>0).reduce((a,b)=>a+b,0),
    losses=-rr.filter(x=>x<0).reduce((a,b)=>a+b,0);
  let equity=1,peak=1,drawdown=0;
  for(const r of rr){equity*=Math.max(0,1+.0025*r);peak=Math.max(peak,equity);drawdown=Math.max(drawdown,1-equity/peak)}
  metrics[key]={trades:n,wins:rr.filter(x=>x>0).length,winRatePct:n?+(rr.filter(x=>x>0).length/n*100).toFixed(2):null,
   totalGrossR:+(rr.reduce((a,b)=>a+b,0)).toFixed(4),
   avgGrossR:n?+(rr.reduce((a,b)=>a+b,0)/n).toFixed(4):null,
   profitFactor:losses?+(gains/losses).toFixed(4):null,
   hypotheticalEquityPct:+((equity-1)*100).toFixed(4),
   maxDrawdownPct:+(drawdown*100).toFixed(4)};
 }
 return {status:"GROSS_ZERO_DEDUCTION_RESEARCH",market:"BINANCE_SPOT_BTCUSDT",
  barMs:bars[0].barMs,barCount:bars.length,trainDays,oosDays,
  assumptions:{transactionCostDeductions:0,feeDeduction:0,slippageDeduction:0,spreadDeduction:0,
   entry:"NEXT_BAR_OPEN",slAtr:stopATR,tpR:rewardR,maxHoldBars:holdingBars,
   sameBarStopTarget:"STOP_FIRST",riskPerTradePct:0.25,accountNetProfit:false},
  metrics,trades:results,executionEnabled:false};
}
if(require.main===module){
 const file=process.argv[2];
 if(!file)throw Error("USAGE: node composite-backtest.cjs bars.json");
 const data=JSON.parse(fs.readFileSync(file,"utf8"));
 const periods={trainDays:["2026-10-20","2026-10-21","2026-10-22","2026-10-23","2026-10-24"],
  oosDays:["2026-11-13","2026-11-14","2026-11-15","2026-11-16","2026-11-17"]};
 const datasets=data.bars||data;
 const all={createdUtc:new Date().toISOString(),source:data.metadata||[],results:{}};
 for(const [tf,bars] of Object.entries(datasets))all.results[tf]=run(bars,periods);
 process.stdout.write(JSON.stringify(all,null,2)+"\n");
}
module.exports={run,atrAt};
