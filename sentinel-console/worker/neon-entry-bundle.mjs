"use strict";
import {neon} from "@neondatabase/serverless";
import research from "./runner.js";
import trader from "./cloud-trader/runner.js";
const {runOnce}=research;
const {runCloudCycle}=trader;
const RESEARCH_TRIGGER="sentinel-autonomy-quarterhour";
const CLOUD_TRIGGER="sentinel-cloud-five-minute";
export default {
 async fetch(request){
  if(request.method!=="POST")return new Response("Method not allowed",{status:405,headers:{Allow:"POST"}});
  const marker=request.headers.get("x-neon-trigger-invocation-id");
  if(!marker||marker.length<8||marker.length>256)return new Response("Unauthorized",{status:401});
  let incoming;
  try{incoming=await request.json()}catch(_){return new Response("Invalid trigger",{status:400})}
  const triggerName=incoming?.trigger?.name;
  if(incoming?.version!==1||incoming?.invocation_id!==marker||
     incoming?.trigger?.type!=="schedule"||
     ![RESEARCH_TRIGGER,CLOUD_TRIGGER].includes(triggerName))
    return new Response("Unauthorized",{status:401});
  if(!process.env.DATABASE_URL)return new Response("Database unavailable",{status:503});
  const sql=neon(process.env.DATABASE_URL);
  if(triggerName===RESEARCH_TRIGGER){
    const result=await runOnce(sql);
    return Response.json({ok:true,service:"sentinel-research",status:result.status,
       totals:result.totals||{},orders_executed:0});
  }
  // Safe non-secret release canary: confirm that the scheduled function has
  // loaded the intended contract-aware cloud trader module.
  console.info(JSON.stringify({event:"sentinel_cloud_pdf_weekly_demo_v1",
    contract_probe_loaded:runCloudCycle.toString().includes("row.contract_status")}));
  let cloud;
  try{cloud=await runCloudCycle(sql)}
  catch(e){cloud={status:"ERROR",reason:String(e?.message||"CLOUD_CYCLE_ERROR").slice(0,80),orders_sent:0}}
  return Response.json({ok:true,service:"sentinel-cloud-demo",status:cloud.status,
    mode:cloud.mode||"SHADOW_ONLY",orders_executed:cloud.orders_sent||0});
 }
};