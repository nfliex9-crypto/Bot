"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const {demoEntryAuthorized,mondayDemoEntryWindow}=require("../worker/cloud-trader/runner.js");
const account={id:"fusion-demo-1964",broker:"mt5",isDemo:true,hot:true};
const env={SENTINEL_CLOUD_MODE:"demo_execution",
 SENTINEL_CLOUD_ENABLE_DEMO:"YES_I_AUTHORIZE_SENTINEL_DEMO_ONLY",
 SENTINEL_CLOUD_UNVERIFIED_TRIAL:"YES_EXPLICIT_DEMO_TRIAL",
 SENTINEL_CLOUD_ACCOUNT_ID:account.id};
const monday=Date.parse("2026-11-23T09:00:00Z");
test("DB pause always blocks demo order path even with legacy execution environment flags",()=>{
 assert.equal(mondayDemoEntryWindow(monday),true);
 assert.equal(demoEntryAuthorized(monday,false,env,account),false);
 assert.equal(demoEntryAuthorized(monday,null,env,account),false);
});
test("future demo entry requires both DB approval and verified demo environment",()=>{
 assert.equal(demoEntryAuthorized(monday,true,env,account),true);
 assert.equal(demoEntryAuthorized(monday,true,{...env,SENTINEL_CLOUD_MODE:"shadow"},account),false);
 assert.equal(demoEntryAuthorized(monday,true,env,{...account,isDemo:false}),false);
 assert.equal(demoEntryAuthorized(Date.parse("2026-11-22T22:59:59Z"),true,env,account),false);
});
