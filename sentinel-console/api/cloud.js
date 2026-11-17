"use strict";
/**
 * Sentinel cloud-only MT5 account link via MetaApi.
 * No local terminal, Windows agent, or broker password in Sentinel.
 * Read-only. Never submit trading orders or deploy paid provider resources.
 */
const crypto = require("node:crypto");
const {neon} = require("@neondatabase/serverless");
const PROVISION = "https://mt-provisioning-api-v1.agiliumtrade.agiliumtrade.ai";
const REGIONS = Object.freeze({
  "new-york": "https://mt-client-api-v1.new-york.agiliumtrade.ai",
  "vint-hill": "https://mt-client-api-v1.new-york.agiliumtrade.ai",
  "london": "https://mt-client-api-v1.london.agiliumtrade.ai"
});
const uuid = x => /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(String(x||""));
const response = (res,status,data) => {
  res.setHeader("Cache-Control","private, no-store, max-age=0");
  res.setHeader("X-Content-Type-Options","nosniff");
  return res.status(status).json(data);
};
const equal = (a,b) => {
  if(typeof a!=="string"||typeof b!=="string"||!a||!b)return false;
  const x=Buffer.from(a),y=Buffer.from(b);
  return x.length===y.length&&crypto.timingSafeEqual(x,y);
};
const sqlDB = () => {
  if(!process.env.DATABASE_URL)throw Error("DATABASE_NOT_CONFIGURED");
  return neon(process.env.DATABASE_URL);
};
const aesKey = () => {
  const hex=String(process.env.MT5_CLOUD_ENCRYPTION_KEY||"");
  if(!/^[0-9a-f]{64}$/i.test(hex))throw Error("ENCRYPTION_NOT_CONFIGURED");
  return Buffer.from(hex,"hex");
};
function seal(value) {
  const iv=crypto.randomBytes(12),cipher=crypto.createCipheriv("aes-256-gcm",aesKey(),iv);
  const encrypted=Buffer.concat([cipher.update(value,"utf8"),cipher.final()]);
  return [iv.toString("base64"),cipher.getAuthTag().toString("base64"),encrypted.toString("base64")].join(".");
}
function unseal(blob) {
  const [iv,tag,body]=String(blob||"").split(".");
  if(!iv||!tag||!body)throw Error("INVALID_SECRET_DATA");
  const decipher=crypto.createDecipheriv("aes-256-gcm",aesKey(),Buffer.from(iv,"base64"));
  decipher.setAuthTag(Buffer.from(tag,"base64"));
  return Buffer.concat([decipher.update(Buffer.from(body,"base64")),decipher.final()]).toString("utf8");
}
async function provider(base,path,token) {
  const url=new URL(path,base);
  if(url.origin!==base)throw Error("PROVIDER_ORIGIN");
  let resp;
  try {
    resp=await fetch(url,{
      method:"GET",headers:{"Accept":"application/json","auth-token":token},
      signal:AbortSignal.timeout(10000),cache:"no-store",redirect:"error"
    });
  } catch (_) { throw Error("PROVIDER_UNAVAILABLE"); }
  let data=null;
  try { data=await resp.json(); } catch (_){}
  if(!resp.ok) {
    if(resp.status===401||resp.status===403)throw Error("METAAPI_AUTH_FAILED");
    if(resp.status===404)throw Error("METAAPI_ACCOUNT_NOT_READY");
    if(resp.status===429)throw Error("METAAPI_RATE_LIMIT");
    throw Error("METAAPI_HTTP_"+resp.status);
  }
  return data;
}
function safeAccount(a) {
  return {
    id:String(a._id||a.id||""),
    name:String(a.name||"MT5 Account").slice(0,75),
    platform:Number(a.version)===5?"MT5":"OTHER",
    server:String(a.server||"").slice(0,90),
    last4:String(a.login||"").slice(-4),
    state:String(a.state||"UNKNOWN"),
    connectionStatus:String(a.connectionStatus||"UNKNOWN"),
    region:String(a.region||"")
  };
}
async function listProvider(token) {
  const data=await provider(PROVISION,"/users/current/accounts?limit=1000",token);
  const all=Array.isArray(data)?data:(Array.isArray(data?.items)?data.items:[]);
  return all.filter(a=>Number(a.version)===5&&uuid(a._id||a.id)).map(safeAccount);
}
async function storedToken(sql) {
  const rows=await sql`SELECT cipher_value FROM sentinel_mt5_cloud_config WHERE config_key='metaapi_token' LIMIT 1`;
  if(!rows.length)throw Error("METAAPI_TOKEN_NOT_CONFIGURED");
  return unseal(rows[0].cipher_value);
}
function rowStatus(r) {
  return {
    id:r.id,provider:"metaapi",name:r.account_label,server:r.broker_server,
    account_last4:r.account_last4,account_state:r.account_state,
    connection_status:r.connection_status,trade_mode:r.verified_trade_mode,
    balance:r.verified_trade_mode==="DEMO"?r.balance:null,
    equity:r.verified_trade_mode==="DEMO"?r.equity:null,
    currency:r.verified_trade_mode==="DEMO"?r.currency:null,
    error_code:r.error_code,last_checked_at:r.last_checked_at,last_verified_at:r.last_verified_at,
    cloud_connected:r.connection_status==="CONNECTED"&&r.verified_trade_mode==="DEMO"
  };
}
async function refreshLinked(sql,row,token) {
  const providerId=String(row.provider_account_id);
  let a,info=null,connection="UNKNOWN",tradeMode="UNKNOWN",last4=null;
  let status="UNKNOWN",server=String(row.broker_server||"");
  try {
    a=await provider(PROVISION,"/users/current/accounts/"+providerId,token);
    if(Number(a.version)!==5)throw Error("NOT_MT5_ACCOUNT");
    connection=String(a.connectionStatus||"UNKNOWN");
    status=String(a.state||"UNKNOWN");
    server=String(a.server||server).slice(0,90);
    last4=String(a.login||"").slice(-4);
    if(status==="DEPLOYED"&&connection==="CONNECTED") {
      const base=REGIONS[String(a.region||"").toLowerCase()];
      if(!base)throw Error("UNSUPPORTED_METAAPI_REGION");
      info=await provider(base,"/users/current/accounts/"+providerId+"/account-information",token);
      // Exact provider enum. Never infer Demo from server name or login number.
      if(info?.type==="ACCOUNT_TRADE_MODE_DEMO")tradeMode="DEMO";
      else if(info?.type==="ACCOUNT_TRADE_MODE_REAL"||info?.type==="ACCOUNT_TRADE_MODE_CONTEST")
        tradeMode="REJECTED_NON_DEMO";
      else throw Error("ACCOUNT_MODE_UNVERIFIED");
    }
    const verified=tradeMode==="DEMO";
    const next=await sql`UPDATE sentinel_mt5_cloud_accounts SET
      broker_server=${server}, account_state=${status},
      connection_status=${connection}, verified_trade_mode=${tradeMode},
      account_last4=${last4},balance=${verified?Number(info?.balance):null},
      equity=${verified?Number(info?.equity):null},
      currency=${verified?String(info?.currency||"USD").slice(0,6):null},
      error_code=${tradeMode==="REJECTED_NON_DEMO"?"ACCOUNT_NOT_DEMO":null},
      last_checked_at=NOW(),
      last_verified_at=CASE WHEN ${verified} THEN NOW() ELSE last_verified_at END
      WHERE id=${row.id} RETURNING id,account_label,broker_server,account_last4,
      account_state,connection_status,verified_trade_mode,balance,equity,currency,
      error_code,last_checked_at,last_verified_at`;
    return rowStatus(next[0]);
  } catch(err){
    const code=String(err.message||"CHECK_FAILED").slice(0,80);
    const next=await sql`UPDATE sentinel_mt5_cloud_accounts SET
      connection_status='UNKNOWN',verified_trade_mode='UNKNOWN',
      balance=NULL,equity=NULL,error_code=${code},last_checked_at=NOW()
      WHERE id=${row.id} RETURNING id,account_label,broker_server,account_last4,
      account_state,connection_status,verified_trade_mode,balance,equity,currency,
      error_code,last_checked_at,last_verified_at`;
    return rowStatus(next[0]);
  }
}
module.exports=async(req,res)=>{
  const action=String(req.query.action||"");
  const reads=new Set(["status","discover"]),writes=new Set(["token","link","refresh","forget-token","unlink"]);
  if((req.method!=="GET"&&!writes.has(action))||(req.method!=="POST"&&!reads.has(action)))
    return response(res,405,{ok:false,error:"METHOD_NOT_ALLOWED"});
  if(!reads.has(action)&&!writes.has(action))
    return response(res,404,{ok:false,error:"UNKNOWN_ACTION"});
  if(!equal(req.headers["x-console-key"],process.env.DASHBOARD_ACCESS_KEY))
    return response(res,401,{ok:false,error:"UNAUTHORIZED"});
  if(JSON.stringify(req.body||"").length>9000)
    return response(res,413,{ok:false,error:"REQUEST_TOO_LARGE"});
  let sql;
  try { sql=sqlDB();aesKey(); } catch(_) {
    return response(res,503,{ok:false,error:"CLOUD_BRIDGE_NOT_CONFIGURED"});
  }
  try {
    if(action==="status"){
      const [keys,rows]=await Promise.all([
        sql`SELECT config_key FROM sentinel_mt5_cloud_config WHERE config_key='metaapi_token'`,
        sql`SELECT id,account_label,broker_server,account_last4,account_state,
          connection_status,verified_trade_mode,balance,equity,currency,
          error_code,last_checked_at,last_verified_at
          FROM sentinel_mt5_cloud_accounts ORDER BY created_at DESC LIMIT 15`
      ]);
      return response(res,200,{ok:true,provider:"MetaApi",token_configured:keys.length>0,
        accounts:rows.map(rowStatus),generated_at:new Date().toISOString()});
    }
    if(action==="token"){
      const token=String(req.body?.token||"").trim();
      if(token.length<16||token.length>2048||!/^[\x21-\x7e]+$/.test(token))
        return response(res,400,{ok:false,error:"TOKEN_FORMAT_INVALID"});
      // Validate API token before storing. No provider/broker credentials in logs.
      const accounts=await listProvider(token);
      const cipher=seal(token);
      await sql`INSERT INTO sentinel_mt5_cloud_config(config_key,cipher_value,updated_at)
        VALUES ('metaapi_token',${cipher},NOW())
        ON CONFLICT(config_key) DO UPDATE SET cipher_value=EXCLUDED.cipher_value,updated_at=NOW()`;
      return response(res,200,{ok:true,token_configured:true,available_mt5_accounts:accounts.length});
    }
    if(action==="forget-token"){
      await sql`DELETE FROM sentinel_mt5_cloud_config WHERE config_key='metaapi_token'`;
      return response(res,200,{ok:true,token_configured:false});
    }
    const token=await storedToken(sql);
    if(action==="discover"){
      const accounts=await listProvider(token);
      return response(res,200,{ok:true,accounts});
    }
    if(action==="link"){
      const id=String(req.body?.provider_account_id||"");
      if(!uuid(id))return response(res,400,{ok:false,error:"INVALID_ACCOUNT_ID"});
      const a=await provider(PROVISION,"/users/current/accounts/"+id,token);
      if(Number(a.version)!==5)return response(res,400,{ok:false,error:"NOT_MT5_ACCOUNT"});
      const name=String(a.name||"MT5").slice(0,75);
      const server=String(a.server||"").slice(0,90);
      const tx=crypto.randomBytes(16).toString("hex");
      const rows=await sql`INSERT INTO sentinel_mt5_cloud_accounts
        (id,provider,account_label,broker_server,provider_account_id,create_transaction_id,
          account_state,connection_status,verified_trade_mode,account_last4)
        VALUES(${crypto.randomUUID()},'metaapi',${name},${server},${id},${tx},
          ${String(a.state||"UNKNOWN")},${String(a.connectionStatus||"UNKNOWN")},'UNKNOWN',
          ${String(a.login||"").slice(-4)})
        ON CONFLICT(provider_account_id) DO UPDATE SET
          account_label=EXCLUDED.account_label,broker_server=EXCLUDED.broker_server
        RETURNING id,provider_account_id,broker_server`;
      const info=await refreshLinked(sql,rows[0],token);
      return response(res,200,{ok:true,account:info});
    }
    if(action==="refresh"){
      const id=String(req.body?.id||"");
      if(!uuid(id))return response(res,400,{ok:false,error:"INVALID_LINKED_ID"});
      const rows=await sql`SELECT id,provider_account_id,broker_server FROM sentinel_mt5_cloud_accounts WHERE id=${id}`;
      if(!rows.length)return response(res,404,{ok:false,error:"LINK_NOT_FOUND"});
      return response(res,200,{ok:true,account:await refreshLinked(sql,rows[0],token)});
    }
    if(action==="unlink"){
      const id=String(req.body?.id||"");
      if(!uuid(id))return response(res,400,{ok:false,error:"INVALID_LINKED_ID"});
      await sql`DELETE FROM sentinel_mt5_cloud_accounts WHERE id=${id}`;
      return response(res,200,{ok:true,unlinked:true});
    }
    return response(res,404,{ok:false,error:"UNKNOWN_ACTION"});
  } catch(err) {
    const code=String(err.message||"SERVER_ERROR");
    const publicErrors=new Set(["METAAPI_TOKEN_NOT_CONFIGURED","METAAPI_AUTH_FAILED",
      "METAAPI_ACCOUNT_NOT_READY","METAAPI_RATE_LIMIT","PROVIDER_UNAVAILABLE",
      "UNSUPPORTED_METAAPI_REGION","NOT_MT5_ACCOUNT"]);
    if(publicErrors.has(code))return response(res,code==="METAAPI_AUTH_FAILED"?401:422,{ok:false,error:code});
    console.error("cloud_bridge_error",code.slice(0,70).replace(/[\r\n]/g,""));
    return response(res,503,{ok:false,error:"CLOUD_BRIDGE_UNAVAILABLE"});
  }
};