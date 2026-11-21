"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const backtest=require("../worker/orderflow/composite-backtest.cjs");
const MS=300000,start=Date.UTC(2026,10,20);
const a=Array.from({length:220},(_,i)=>{
 const open=60000+i*.5,close=open+.25;
 return {openTime:start+i*MS,closeTime:start+(i+1)*MS,barMs:MS,
  sourceQuality:"VERIFIED_AGGRESSOR_TRADES",closed:true,venue:"BINANCE_SPOT",
  symbol:"BTCUSDT",sessionId:"BINANCE_SPOT_BTCUSDT_UTC",
  open,high:close+.3,low:open-.3,close,delta:i%2?25:-20};
});
test("gross-only backtest never deducts spread, commission, swap or slippage fields",()=>{
 const p={trainDays:["2026-10-20"],oosDays:[]};
 const baseline=backtest.run(a,p);
 const augmented=a.map((b)=>({...b,spread:100,commission:300,swap:800,slippage:1400}));
 const rerun=backtest.run(augmented,p);
 assert.deepEqual(rerun,baseline);
 assert.equal(baseline.assumptions.transactionCostDeductions,0);
 assert.equal(baseline.assumptions.spreadDeduction,0);
 assert.equal(baseline.assumptions.feeDeduction,0);
 assert.equal(baseline.assumptions.slippageDeduction,0);
 assert.equal(baseline.executionEnabled,false);
});
test("gross research rejects counterfeit price-only bars and partial candles",()=>{
 const p={trainDays:["2026-10-20"]};
 assert.throws(()=>backtest.run(a.map(b=>({...b,sourceQuality:"MT5_TICK_VOLUME"})),p),/UNVERIFIED_BARS/);
 assert.throws(()=>backtest.run(a.map((b,i)=>i===13?{...b,closed:false}:b),p),/UNVERIFIED_BARS/);
});
