"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const f=require("../brain/purged-forward-evidence.js");
const day=86400000,base=Date.UTC(2026,7,1);
function trade(i,overrides={}){
 const open=base+i*day;
 return {accountId:"fusion-demo-A",ticket:"T"+i,symbol:"XAUUSD",
  family:"pdf_sweep_bos",isDemo:true,brokerVerified:true,complete:true,
  partial:false,openTime:new Date(open).toISOString(),
  closeTime:new Date(open+3600000).toISOString(),
  taggedAt:new Date(open-3600000).toISOString(),
  grossProfit:i%3===0?-10:20,riskAtEntry:10,...overrides};
}
const options={asOf:Date.UTC(2026,10,22),embargoMs:3600000,minTrain:1,minOos:1,minOosDays:1};
test("65/35 chronological gross split remains deterministic without overlap",()=>{
 const input=Array.from({length:80},(_,i)=>trade(i));
 const a=f.evaluate(input,options),b=f.evaluate([...input].reverse(),options);
 assert.deepEqual(a,b);
 assert.equal(a.strategies[0].train.trades,52);
 assert.equal(a.strategies[0].oos.trades,28);
 assert.equal(a.strategies[0].purgedTrainTrades,0);
 assert.equal(a.costDeductions,0);
 assert.equal(a.ordersEnabled,false);
});
test("purges train labels closing inside OOS and applies a real embargo",()=>{
 const input=Array.from({length:40},(_,i)=>trade(i));
 // 40*.65 = 26; OOS starts day 26. This trade starts on day 25
 // but its label resolves two days into the held-out future.
 input[25]={...input[25],closeTime:new Date(base+27*day).toISOString()};
 const x=f.evaluate(input,options).strategies[0];
 assert.equal(x.train.trades,25);
 assert.equal(x.oos.trades,14);
 assert.equal(x.purgedTrainTrades,1);
 assert.ok(Date.parse(x.lastTrainClose)+3600000<=Date.parse(x.firstOosOpen));
});
test("isolates accounts, symbols and families before learning",()=>{
 const input=[
  ...Array.from({length:30},(_,i)=>trade(i,{accountId:"A",symbol:"XAUUSD"})),
  ...Array.from({length:30},(_,i)=>trade(i,{accountId:"B",symbol:"XAUUSD"})),
  ...Array.from({length:30},(_,i)=>trade(i,{accountId:"A",symbol:"BTCUSD",family:"pdf_fvg_retest",ticket:"BTC"+i}))
 ];
 const x=f.evaluate(input,options);
 assert.equal(x.strategies.length,3);
 assert.equal(x.accepted,90);
 assert.ok(x.strategies.every(s=>s.train.trades===19&&s.oos.trades===11));
});
test("forged pre-entry labels, absent entry-risk, incomplete or future fills do not teach",()=>{
 const rows=[trade(0),trade(1,{taggedAt:trade(1).closeTime}),
  trade(2,{riskAtEntry:null}),trade(3,{brokerVerified:false}),
  trade(4,{isDemo:false}),trade(5,{complete:false}),
  trade(6,{closeTime:"2027-01-01T00:00:00.000Z"}),trade(0)];
 const out=f.evaluate(rows,options);
 assert.equal(out.accepted,1);assert.equal(out.rejected,7);
 assert.equal(out.strategies[0].status,"COLLECTING_FORWARD");
});
test("duplicate tickets across different accounts allowed; same-account duplicate rejected",()=>{
 const rows=[trade(0),trade(0,{accountId:"second"}),trade(0,{grossProfit:999})];
 const out=f.evaluate(rows,options);
 assert.equal(out.accepted,2);assert.equal(out.rejected,1);
 assert.equal(out.strategies.length,2);
});
test("hypothetical fee or spread columns never alter gross evidence",()=>{
 const raw=Array.from({length:75},(_,i)=>trade(i));
 const weird=raw.map(x=>({...x,spread:9999,commission:-2000,swap:-300,slippage:300}));
 assert.deepEqual(f.evaluate(raw,options),f.evaluate(weird,options));
});
test("unverified strategy names cannot become learned families",()=>{
 const out=f.evaluate([trade(0,{family:"made_up_instructor_strategy"})],options);
 assert.equal(out.accepted,0);assert.equal(out.rejected,1);
});
