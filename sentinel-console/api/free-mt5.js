"use strict";
/**
 * Sentinel zero-subscription MT5 DEMO bridge (TickerAll Free).
 * Does not store broker password, access trading APIs, connect live accounts,
 * or enable any paid "always-hot" option.
 */
const crypto = require("node:crypto");
const {neon} = require("@neondatabase/serverless");
const PROVIDER = "https://api.tickerall.com";
const safe = (s,n=100)=>String(s??"").slice(0,n);
const reply=(res,status,body)=>{
 res.setHeader("Cache-Control","private, no-store, max-age=0");
 res.setHeader("X-Content-Type-Options","nosniff");
 return res.status(status).json(body);
};
const same=(a,b)=>{
 if(!a||!b||typeof a!=="string"||typeof b!=="string")return false;
 const x=Buffer.from(a),y=Buffer.from(b);
 return x.length===y.length&&crypto.timingSafeEqual(x,y);
};
function db(){
 if(!process.env.DATABASE_URL)throw Error("NOT_CONFIGURED");
 return neon(process.env.DATABASE_URL);
}
function encryptionKey(){
 const v=String(process.env.MT5_CLOUD_ENCRYPTION_KEY||"");
 if(!/^[0-9a-f]{64}$/i.test(v))throw Error("NOT_CONFIGURED");
 return Buffer.from(v,"hex");
}
function encrypt(value){
 const iv=crypto.randomBytes(12);
 const cipher=crypto.createCipheriv("aes-256-gcm",encryptionKey(),iv);
 const data=Buffer.concat([cipher.update(value,"utf8"),cipher.final()]);
 return [iv,cipher.getAuthTag(),data].map(x=>x.toString("base64")).join(".");
}
function decrypt(value){
 const parts=String(value||"").split(".");
 if(parts.length!==3)throw Error("ENCRYPTION_ERROR");
 const dec=crypto.createDecipheriv("aes-256-gcm",encryptionKey(),Buffer.from(parts[0],"base64"));
 dec.setAuthTag(Buffer.from(parts[1],"base64"));
 return Buffer.concat([dec.update(Buffer.from(parts[2],"base64")),dec.final()]).toString("utf8");
}
async function request(path,token,method="GET",body=null){
 if(!/^\/(?:v1\/accounts(?:\/[A-Za-z0-9_-]+)?|v1\/sessions)$/.test(path))throw Error("INVALID_PATH");
 const headers={Authorization:"Bearer "+token,Accept:"application/json"};
 if(body!==null)headers["Content-Type"]="application/json";
 let response;
 try{
   response=await fetch(PROVIDER+path,{
    method,headers,body:body!==null?JSON.stringify(body):undefined,
    signal:AbortSignal.timeout(10000),redirect:"error",cache:"no-store"
   });
 }catch(_){throw Error("TICKERALL_UNREACHABLE")}
 let data={};
 try{data=await response.json()}catch(_){}
 if(!response.ok){
  if(response.status===401||response.status===403)throw Error("TICKERALL_KEY_REJECTED");
  if(response.status===429)throw Error("TICKERALL_RATE_LIMIT");
  if(response.status===409)throw Error(safe(data.code||data.error||"BROKER_SESSION_COLD",75));
  throw Error("TICKERALL_HTTP_"+response.status);
 }
 return data;
}
async function tokenFor(sql){
 const rows=await sql`SELECT cipher_value FROM sentinel_mt5_cloud_config WHERE config_key='tickerall_api_token' LIMIT 1`;
 if(!rows.length)throw Error("TICKERALL_TOKEN_MISSING");
 return decrypt(rows[0].cipher_value);
}
function minimalAccount(a){
 // Demo mode is never inferred from the broker server name.
 if(a?.broker!=="mt5")return null;
 const isDemo=a.isDemo===true;
 return {
  id:safe(a.id,100),broker:"mt5",server:safe(a.server,90),
  accountNumber:safe(a.accountNumber,32),
  isDemo,blocked:!isDemo,
  hot:a.hot===true,status:safe(a.status,40),
  lastHotAt:a.lastHotAt||null
 };
}
function snapshot(a){
 const isDemo=a?.broker==="mt5"&&a?.isDemo===true&&a?.account?.accountType==="demo";
 const online=isDemo&&String(a.status||"").toLowerCase()==="online";
 const raw=a?.account||{};
 const val=x=>typeof x==="number"&&Number.isFinite(x)?x:null;
 return {
  id:safe(a.id,100),broker:"mt5",server:safe(a.server,90),
  accountNumber:safe(a.accountNumber,32),isDemo,online,
  balance:online?val(raw.balance):null,
  equity:online?val(raw.equity):null,
  currency:online?safe(raw.currency,8):null,
  leverage:online?val(raw.leverage):null,
  positions:online&&Array.isArray(a.positions)?a.positions.slice(0,50).map(p=>({
   ticket:p.ticket,symbol:safe(p.symbol,26),side:safe(p.side,8),
   volume:val(p.volume),profit:val(p.profit)
  })):[],
  status:online?"ONLINE":safe(a.status||"UNKNOWN",50),
  checkedAt:new Date().toISOString()
 };
}
module.exports=async(req,res)=>{
 const action=String(req.query?.action||"");
 const methods={
  status:"GET",saveKey:"POST",forgetKey:"POST",
  connect:"POST",inspect:"POST",disconnect:"POST"
 };
 if(!Object.prototype.hasOwnProperty.call(methods,action))return reply(res,404,{ok:false,error:"UNKNOWN_ACTION"});
 if(req.method!==methods[action])return reply(res,405,{ok:false,error:"METHOD_NOT_ALLOWED"});
 if(!same(req.headers["x-console-key"],process.env.DASHBOARD_ACCESS_KEY))
    return reply(res,401,{ok:false,error:"UNAUTHORIZED"});
 if(JSON.stringify(req.body||"").length>5000)return reply(res,413,{ok:false,error:"REQUEST_TOO_LARGE"});
 let sql;
 try{sql=db();encryptionKey()}catch(_){return reply(res,503,{ok:false,error:"BRIDGE_NOT_CONFIGURED"})}
 try{
  if(action==="saveKey"){
    const key=String(req.body?.apiKey||"").trim();
    if(!/^cf_api_[A-Za-z0-9_-]{10,512}$/.test(key))
      return reply(res,400,{ok:false,error:"INVALID_TICKERALL_API_KEY"});
    // Verify the key and product access before encryption.
    await request("/v1/accounts",key);
    await sql`INSERT INTO sentinel_mt5_cloud_config(config_key,cipher_value,updated_at)
      VALUES('tickerall_api_token',${encrypt(key)},NOW())
      ON CONFLICT(config_key) DO UPDATE SET
      cipher_value=EXCLUDED.cipher_value,updated_at=NOW()`;
    return reply(res,200,{ok:true,configured:true});
  }
  if(action==="forgetKey"){
    await sql`DELETE FROM sentinel_mt5_cloud_config WHERE config_key='tickerall_api_token'`;
    return reply(res,200,{ok:true,configured:false});
  }
  if(action==="status"){
    const rows=await sql`SELECT config_key FROM sentinel_mt5_cloud_config
      WHERE config_key='tickerall_api_token' LIMIT 1`;
    if(!rows.length)return reply(res,200,{ok:true,provider:"TickerAll",configured:false,accounts:[]});
    const token=await tokenFor(sql);
    const fetched=await request("/v1/accounts",token);
    const accounts=(Array.isArray(fetched)?fetched:fetched?.accounts||[])
       .map(minimalAccount).filter(Boolean);
    return reply(res,200,{ok:true,provider:"TickerAll",configured:true,accounts,
       generatedAt:new Date().toISOString(),subscriptionCost:"$0 demo/free plan"});
  }
  const token=await tokenFor(sql);
  if(action==="connect"){
    const account=String(req.body?.account||"").trim();
    const password=String(req.body?.password||"");
    const server=String(req.body?.server||"").trim();
    if(!/^\d{4,16}$/.test(account)||password.length<1||password.length>256||
       server.length<2||server.length>128||!/^[\w\s.:-]+$/.test(server))
      return reply(res,400,{ok:false,error:"INVALID_BROKER_CREDENTIAL_FIELDS"});
    const data=await request("/v1/sessions",token,"POST",{
      broker:"mt5",server,account,password,terminalType:"MOBILE"
    });
    if(data?.isDemo!==true)return reply(res,403,{ok:false,error:"DEMO_ONLY_CONNECTION_REQUIRED"});
    return reply(res,200,{ok:true,accountId:safe(data.accountId,100),
      isDemo:true,status:safe(data.status,40),
      expiresAt:data.expiresAt||null});
  }
  const accountId=String(req.body?.accountId||"");
  if(!/^acc_[A-Za-z0-9_-]{3,100}$/.test(accountId))
    return reply(res,400,{ok:false,error:"INVALID_ACCOUNT_ID"});
  if(action==="inspect"){
    const account=await request("/v1/accounts/"+accountId,token);
    const state=snapshot(account);
    if(!state.isDemo)return reply(res,403,{ok:false,error:"NOT_A_VERIFIED_DEMO_ACCOUNT"});
    return reply(res,200,{ok:true,account:state});
  }
  if(action==="disconnect"){
    // Explicit user action. This only removes the provider connection, not broker positions.
    const accounts=await request("/v1/accounts",token);
    const existing=(Array.isArray(accounts)?accounts:accounts?.accounts||[])
       .find(a=>a.id===accountId&&a.isDemo===true&&a.broker==="mt5");
    if(!existing)return reply(res,403,{ok:false,error:"DEMO_ACCOUNT_NOT_FOUND"});
    await request("/v1/accounts/"+accountId,token,"DELETE");
    return reply(res,200,{ok:true,disconnected:true});
  }
 }catch(e){
  const code=safe(e?.message||"UNKNOWN",75);
  const known=new Set(["TICKERALL_TOKEN_MISSING","TICKERALL_KEY_REJECTED",
    "TICKERALL_RATE_LIMIT","TICKERALL_UNREACHABLE","BROKER_ACCOUNT_NOT_HOT",
    "BROKER_SESSION_COLD","FREE_TIER_LIVE_REJECTED"]);
  return reply(res,known.has(code)?422:502,{ok:false,error:known.has(code)?code:"PROVIDER_ERROR"});
 }
};
