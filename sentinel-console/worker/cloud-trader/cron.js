"use strict";
/* One-shot private cloud DEMO monitor; defaults to NO ORDERS. */
const {neon}=require("@neondatabase/serverless");
const {runCloudCycle}=require("./runner.js");
(async()=>{
 if(!process.env.DATABASE_URL)throw Error("DATABASE_URL_REQUIRED");
 const r=await runCloudCycle(neon(process.env.DATABASE_URL));
 console.log(JSON.stringify({service:"sentinel-cloud-trader",status:r.status,reason:r.reason,mode:r.mode,orders_sent:r.orders_sent||0}));
 if(r.status==="ERROR")process.exitCode=1;
})().catch(e=>{console.error("sentinel-cloud-trader:",String(e?.message||e).slice(0,65));process.exitCode=1});
