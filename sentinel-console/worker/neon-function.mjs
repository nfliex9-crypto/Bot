"use strict";
import {createRequire} from "node:module";
const require=createRequire(import.meta.url);
const {neon}=require("@neondatabase/serverless");
const {runOnce}=require("./runner.js");

// Neon Functions trigger-only entrypoint. The Neon gateway strips client-supplied
// x-neon-* headers before setting its verified invocation marker.
export default {
  async fetch(request) {
    if(request.method!=="POST")
      return new Response("Method not allowed",{status:405,headers:{"Allow":"POST"}});
    const marker=request.headers.get("x-neon-trigger-invocation-id");
    if(!marker||marker.length<8||marker.length>256)
      return new Response("Unauthorized",{status:401});
    let incoming;
    try{incoming=await request.json()}catch(_){return new Response("Invalid trigger",{status:400})}
    if(incoming?.version!==1||incoming?.invocation_id!==marker||
       incoming?.trigger?.type!=="schedule"||
       incoming?.trigger?.name!=="sentinel-autonomy-quarterhour")
      return new Response("Unauthorized",{status:401});
    if(!process.env.DATABASE_URL)return new Response("Database unavailable",{status:503});
    const result=await runOnce(neon(process.env.DATABASE_URL));
    return Response.json({ok:true,status:result.status,
      orders_executed:0,totals:result.totals||null});
  }
};
