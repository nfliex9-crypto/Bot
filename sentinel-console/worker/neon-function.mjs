"use strict";
import {createRequire} from "node:module";
const require=createRequire(import.meta.url);
const {neon}=require("@neondatabase/serverless");
const {runOnce}=require("./runner.js");
const {runCloudCycle}=require("./cloud-trader/runner.js");

// Neon Functions accepts only authenticated scheduled trigger invocations.
// The cloud loop has its own lease and is SHADOW_ONLY by default.
export default {
 async fetch(request) {
  if(request.method!=="POST")return new Response("Method not allowed",{status:405,headers:{Allow:"POST"}});
  const marker=request.headers.get("x-neon-trigger-invocation-id");
  if(!marker||marker.length<8||marker.length>256)return new Response("Unauthorized",{status:401});
  let incoming;
  try{incoming=await request.json()}catch(_){return new Response("Invalid trigger",{status:400})}
  if(incoming?.version!==1||incoming?.invocation_id!==marker||
     incoming?.trigger?.type!=="schedule"||
     incoming?.trigger?.name!=="sentinel-autonomy-quarterhour")
    return new Response("Unauthorized",{status:401});
  if(!process.env.DATABASE_URL)return new Response("Database unavailable",{status:503});
  const sql=neon(process.env.DATABASE_URL);
  const research=await runOnce(sql);
  let cloud;
  try{cloud=await runCloudCycle(sql)}
  catch(e){cloud={status:"ERROR",reason:String(e?.message||"CLOUD_CYCLE_ERROR").slice(0,80),orders_sent:0}}
  return Response.json({ok:true,service:"sentinel",
    research_status:research.status,cloud_status:cloud.status,
    cloud_mode:cloud.mode||"SHADOW_ONLY",orders_executed:cloud.orders_sent||0});
 }
};