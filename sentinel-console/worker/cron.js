"use strict";
const {neon}=require("@neondatabase/serverless");
const {runOnce}=require("./runner.js");
const {runCloudCycle}=require("./cloud-trader/runner.js");
(async()=>{
  if(!process.env.DATABASE_URL)throw Error("DATABASE_URL_REQUIRED");
  const sql=neon(process.env.DATABASE_URL);
  const result=await runOnce(sql);
  try{
    const cloud=await runCloudCycle(sql);
    console.log(JSON.stringify({service:"sentinel-cloud-trader",event:"cloud_demo_monitor",status:cloud.status,mode:cloud.mode,orders_sent:cloud.orders_sent||0}));
  }catch(e){console.error(JSON.stringify({service:"sentinel-cloud-trader",event:"monitor_error",code:String(e?.message||"UNKNOWN").slice(0,70)}))}
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
