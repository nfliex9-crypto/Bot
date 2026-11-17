// Sentinel MT5 Control | server-side allowlisted gateway.
// The browser never receives the broker API URL or its credentials.
const { timingSafeEqual } = require("node:crypto");

const ROUTES = Object.freeze({
  connection: ["GET", "/health"],
  status: ["GET", "/api/v1/bot/status"],
  config: ["GET", "/api/v1/bot/config"],
  overview: ["GET", "/api/v1/dashboard/overview"],
  equity: ["GET", "/api/v1/dashboard/equity"],
  trades: ["GET", "/api/v1/dashboard/trades"],
  signals: ["GET", "/api/v1/dashboard/signals"],
  metrics: ["GET", "/api/v1/dashboard/metrics"],
  sessions: ["GET", "/api/v1/dashboard/sessions"],
  symbols: ["GET", "/api/v1/dashboard/symbols"],
  performance: ["GET", "/api/v1/performance/summary"],
  risk: ["GET", "/api/v1/performance/risk-metrics"],
  guards: ["GET", "/api/v1/monitoring/guards"],
  model: ["GET", "/api/v1/training/status"],
  registry: ["GET", "/api/v1/training/registry"],
  backtestresults: ["GET", "/api/v1/backtesting/results"],
  start: ["POST", "/api/v1/bot/start"],
  stop: ["POST", "/api/v1/bot/stop"],
  pause: ["POST", "/api/v1/bot/pause"],
  resume: ["POST", "/api/v1/bot/resume"],
  resetsession: ["POST", "/api/v1/bot/reset-session"],
  backtest: ["POST", "/api/v1/backtesting/run"],
  train: ["POST", "/api/v1/training/train"],
  reload: ["POST", "/api/v1/training/reload"]
});
const COMMANDS = new Set(["start","stop","pause","resume","resetsession","backtest","train","reload"]);

function fail(res, code, message) {
  res.status(code).json({ ok:false, error:message });
}
function authorized(key, provided) {
  if (!key || !provided || typeof provided !== "string") return false;
  const x = Buffer.from(key);
  const y = Buffer.from(provided);
  return x.length === y.length && timingSafeEqual(x,y);
}
function endpoint() {
  const base = (process.env.BOT_API_URL || "").trim().replace(/\/+$/, "");
  if (!base) return null;
  const parsed = new URL(base);
  if (parsed.protocol !== "https:") throw Error("BOT_API_URL must use HTTPS");
  if (parsed.username || parsed.password || parsed.search || parsed.hash) throw Error("BOT_API_URL cannot include credentials or query");
  return parsed.origin;
}
async function upstream(base,path, method="GET", body=null) {
  const url = new URL(path,base);
  if(url.origin!==base) throw Error("Upstream origin mismatch");
  const headers = {"Accept":"application/json"};
  if (process.env.BOT_API_TOKEN) headers.Authorization="Bearer "+process.env.BOT_API_TOKEN;
  if (body!==null) headers["Content-Type"]="application/json";
  const response=await fetch(url,{
    method,headers,
    body:body!==null?JSON.stringify(body):undefined,
    signal:AbortSignal.timeout(10000),
    cache:"no-store",
    redirect:"error"
  });
  let result=null;
  try { result=await response.json(); } catch (_) { result={detail:"Non-JSON upstream response"}; }
  return {status:response.status, result};
}
function payloadFor(op,source) {
  const b=source && typeof source==="object" && !Array.isArray(source) ? source:{};
  if(op==="backtest") {
    if(b.acknowledge_synthetic!==true) throw Error("Backtesting currently uses SYNTHETIC candles. Explicit acknowledgement required.");
    const sym=String(b.symbol||"XAUUSD").toUpperCase().replace(/[^A-Z0-9._]/g,"").slice(0,24);
    return {
      symbol:sym,
      market_type: sym.includes("BTC")||sym.includes("ETH")?"crypto":"forex",
      initial_balance: Math.min(1000000,Math.max(100,Number(b.initial_balance)||5000)),
      risk_per_trade: Math.min(.02,Math.max(.001,Number(b.risk_per_trade)||.005)),
      min_ai_confidence:Math.min(.95,Math.max(.4,Number(b.min_ai_confidence)||.65)),
      n_candles_m5:Math.min(20000,Math.max(200,Number(b.n_candles_m5)||2000)),
      spread_multiplier:Math.min(5,Math.max(.5,Number(b.spread_multiplier)||1)),
      slippage_factor:Math.min(2,Math.max(0,Number(b.slippage_factor)||.3)),
      use_session_filter: Boolean(b.use_session_filter),
      random_seed:42
    };
  }
  if(op==="train") {
    // Train only from actual recorded trades, no silent synthetic samples.
    return {days_history:Math.min(730,Math.max(7,Number(b.days_history)||180)), synthetic_samples:0,
      n_estimators:Math.min(1000,Math.max(50,Number(b.n_estimators)||200)),
      max_depth:Math.min(30,Math.max(3,Number(b.max_depth)||10)),calibrate:true,save:true};
  }
  return null;
}
module.exports = async (req,res) => {
  res.setHeader("Cache-Control","no-store, max-age=0");
  res.setHeader("X-Content-Type-Options","nosniff");
  if(req.method!=="GET"&&req.method!=="POST")return fail(res,405,"Method not allowed");
  const expected=process.env.DASHBOARD_ACCESS_KEY;
  if(!expected) return fail(res,503,"Dashboard access key is not configured");
  if(!authorized(expected,req.headers["x-console-key"]))return fail(res,401,"Invalid console access key");
  const op=String(req.query.op||"").toLowerCase();
  const target=ROUTES[op];
  if(!target)return fail(res,404,"Unknown operation");
  if(req.method!==target[0])return fail(res,405,"Incorrect operation method");
  let base;
  try { base=endpoint(); } catch(_) {return fail(res,503,"Invalid upstream gateway configuration");}
  if(!base)return res.status(503).json({ok:false,connected:false,error:"No bot API connected. Set BOT_API_URL on Vercel."});
  try {
    if(COMMANDS.has(op)){
      const config=await upstream(base,"/api/v1/bot/config");
      if(config.status!==200)return fail(res,502,"Cannot verify bot account mode; command refused");
      const mode=String(config.result?.trading_mode||"unknown").toLowerCase();
      if(!["demo","paper"].includes(mode))return fail(res,403,"Only verified DEMO or PAPER bots can be controlled. Detected: "+mode);
      if(op==="backtest" && req.body?.acknowledge_synthetic!==true)return fail(res,400,"Confirm synthetic backtest data before running");
    }
    let body=null;
    if(op==="backtest"||op==="train")body=payloadFor(op,req.body);
    const answer=await upstream(base,target[1],req.method,body);
    return res.status(answer.status).json({ok:answer.status>=200&&answer.status<300,source:"connected-bot",data:answer.result});
  } catch(err){
    if(/acknowledgement|required|must/.test(err.message))return fail(res,400,err.message);
    return fail(res,502,"Unable to reach bot API. Check backend health and TLS.");
  }
};