"use strict";
const {neon}=require("@neondatabase/serverless");
const {runOnce}=require("./runner.js");
(async()=>{
  if(!process.env.DATABASE_URL)throw Error("DATABASE_URL_REQUIRED");
  const result=await runOnce(neon(process.env.DATABASE_URL));
  console.log(JSON.stringify({
   service:"sentinel-autonomy",event:"cron_research",
   status:result.status,totals:result.totals||{},orders_executed:0
  }));
  if(result.status==="ERROR")process.exitCode=1;
})().catch(e=>{
  console.error(JSON.stringify({service:"sentinel-autonomy",
   event:"cron_error",code:String(e?.message||"UNKNOWN").slice(0,90)}));
  process.exitCode=1;
});
