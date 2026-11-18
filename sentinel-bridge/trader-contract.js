"use strict";
/* Owner-facing demo telemetry only: NEVER a remote order or strategy command. */
const safeName=x=>typeof x==="string"&&/^[A-Za-z0-9._#-]{2,24}$/.test(x);
const STATES=new Set(["RESEARCH_SIGNAL","NO_SIGNAL_OR_STALE_MARKET","BROKER_ACK_AWAITING_RECONCILIATION",
 "BROKER_OUTCOME_UNKNOWN","UNRESOLVED_BROKER_INTENT","DAILY_DRAWDOWN_LOCK","POSITION_CAP_OR_SYMBOL_BUSY",
 "FOREIGN_POSITION_OR_PENDING_ORDER","DUPLICATE_SIGNAL_IDEMPOTENT_SKIP","ORDER_CHECK_REJECTED",
 "BROKER_REJECTED","CONFIG_OR_ACCOUNT_NOT_READY","MT5_TRADING_DISABLED","BROKER_STATE_UNAVAILABLE",
 "DEMO_CONNECTION_LOST","SYMBOL_NOT_FULLY_TRADABLE","BAD_OR_STALE_QUOTE","SPREAD_TOO_WIDE",
 "BROKER_STOP_LEVEL_CONFLICT","NATIVE_RISK_TOO_SMALL_FOR_MIN_LOT","FILLING_MODE_UNSUPPORTED",
 "DEMO_IDENTITY_CHANGED_BEFORE_ORDER","STEP_EXCEPTION","ORDER_CHECK_FAILED",
 "INVALID_STRATEGY_SIGNAL","BRAIN_EVIDENCE_NOT_APPROVED","SIGNAL_TOO_OLD_FOR_ENTRY",
 "BROKER_DOM_CONFIRMATION_MISSING"]);
const BRAIN_STATES=new Set(["NO_APPROVED_SENTINEL_BRAIN_CANDIDATE","DEMO_TRIAL_NOT_LOCALLY_AUTHORIZED",
 "LOCAL_UNVERIFIED_DEMO_TRIAL","BRAIN_EVIDENCE_APPROVED_FOR_DEMO","RESEARCH_APPROVAL_INVALID",
 "RESEARCH_APPROVAL_UNAVAILABLE","RESEARCH_APPROVAL_ACCOUNT_MISMATCH",
 "RESEARCH_APPROVAL_EXPIRED_OR_FUTURE","RESEARCH_EVIDENCE_INCOMPLETE",
 "RESEARCH_EVIDENCE_NOT_POSITIVE","INVALID_STRATEGY_POLICY"]);
const BOOK_STATES=new Set(["NOT_REQUESTED","BROKER_DOM_OBSERVED","BROKER_DOM_NOT_OFFERED",
 "BROKER_DOM_EMPTY","BROKER_DOM_INVALID_LEVEL","BROKER_DOM_ONE_SIDE_MISSING",
 "BROKER_DOM_CROSSED","BROKER_DOM_NON_MONOTONIC_TIME","BROKER_DOM_READ_ERROR"]);
function normalize(payload,now=Date.now()){
 if(payload?.source!=="SENTINEL_INDEPENDENT_TRADER"||
    !["research","demo_execution"].includes(payload?.mode)||
    typeof payload?.execution_armed!=="boolean"||
    !/^[0-9]{1,4}$/.test(payload?.account_last4||""))return null;
 const at=Date.parse(String(payload.timestamp||""));
 if(!Number.isFinite(at)||at>now+10000||now-at>90000)return null;
 if(!Array.isArray(payload.symbols)||payload.symbols.length>8)return null;
 if(!["verified_only","demo_trial",undefined].includes(payload.strategy_policy))return null;
 if(!["off","observe","confirm",undefined].includes(payload.orderbook_mode))return null;
 const rows=[];
 for(const r of payload.symbols){
  if(!safeName(r?.symbol)||!STATES.has(r?.status)||
    (r?.side!==undefined&&!["LONG","SHORT"].includes(r.side))||
    (r?.strategy!==undefined&&!["trend_pullback","donchian_breakout"].includes(r.strategy))||
    (r?.order_submissions!==undefined&&r.order_submissions!==0&&r.order_submissions!==1)||
    (r?.brain_status!==undefined&&!BRAIN_STATES.has(r.brain_status))||
    (r?.orderbook_status!==undefined&&!BOOK_STATES.has(r.orderbook_status))||
    (r?.book_samples!==undefined&&(!Number.isInteger(r.book_samples)||r.book_samples<0||r.book_samples>30))||
    (r?.book_imbalance!==undefined&&(typeof r.book_imbalance!=="number"||!Number.isFinite(r.book_imbalance)||Math.abs(r.book_imbalance)>1))||
    (r?.book_persistent_side!==undefined&&![-1,0,1].includes(r.book_persistent_side)))return null;
  rows.push({symbol:r.symbol,status:r.status,
    ...(r.side?{side:r.side}:{}),...(r.strategy?{strategy:r.strategy}:{}),
    order_submissions:r.order_submissions===1?1:0,
    ...(r.brain_status?{brain_status:r.brain_status}:{}),
    ...(r.orderbook_status?{orderbook_status:r.orderbook_status}:{}),
    ...(r.book_imbalance!==undefined?{book_imbalance:r.book_imbalance}:{}),
    ...(r.book_samples!==undefined?{book_samples:r.book_samples}:{}),
    ...(r.book_persistent_side!==undefined?{book_persistent_side:r.book_persistent_side}:{})});
 }
 return {source:"SENTINEL_INDEPENDENT_TRADER",mode:payload.mode,
  execution_armed:payload.execution_armed,account_last4:payload.account_last4,
  strategy_policy:payload.strategy_policy||"verified_only",
  orderbook_mode:payload.orderbook_mode||"off",
  observed_at:new Date(at).toISOString(),symbols:rows,
  execution_proof:"UNVERIFIED_DEVICE_TELEMETRY_NOT_BROKER_FILL_CONFIRMATION"};
}
module.exports={normalize};
