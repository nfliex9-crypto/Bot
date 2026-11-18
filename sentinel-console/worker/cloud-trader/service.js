"use strict";
/* Optional dedicated cloud-trader polling process. Does NOT start on deploy.
 * The existing research worker still invokes runCloudCycle every ~15 min.
 * This independent process improves demo shadow freshness when explicitly run.
 */
const SERVICE="sentinel-cloud-trader";
const INTERVAL_MS=60_000;
const safe=x=>String(x||"UNKNOWN").replace(/[\x00-\x1f]/g," ").slice(0,65);
function sleepDuration(elapsed,interval=INTERVAL_MS){
 if(!Number.isFinite(elapsed)||elapsed<0)return interval;
 return Math.max(1_000,interval-elapsed);
}
async function main(){
 if(!process.env.DATABASE_URL)throw Error("DATABASE_URL_REQUIRED");
 const {neon}=require("@neondatabase/serverless");
 const {runCloudCycle}=require("./runner.js");
 const sql=neon(process.env.DATABASE_URL);
 let stop=false;
 process.on("SIGINT",()=>{stop=true});
 process.on("SIGTERM",()=>{stop=true});
 console.log(JSON.stringify({service:SERVICE,event:"started",mode:process.env.SENTINEL_CLOUD_MODE||"SHADOW_ONLY",orders_enabled_by_default:false}));
 while(!stop){
  const started=Date.now();
  try{
   const r=await runCloudCycle(sql);
   console.log(JSON.stringify({service:SERVICE,event:"cycle",status:r.status,reason:safe(r.reason),orders_sent:r.orders_sent||0,account_last4:r.account_last4||null}));
  }catch(e){
   console.error(JSON.stringify({service:SERVICE,event:"cycle_error",error:safe(e.message)}));
  }
  const until=Date.now()+sleepDuration(Date.now()-started);
  while(!stop&&Date.now()<until){
   await new Promise(resolve=>setTimeout(resolve,Math.min(2000,until-Date.now())));
  }
 }
 console.log(JSON.stringify({service:SERVICE,event:"stopped"}));
}
if(require.main===module)main().catch(e=>{console.error(safe(e.message));process.exitCode=1});
module.exports={sleepDuration,INTERVAL_MS};
