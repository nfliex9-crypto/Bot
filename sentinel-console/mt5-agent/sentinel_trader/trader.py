"""Sentinel's OWN DEMO MT5 trader. No dependence on the existing Grok process.

Broker order submission is doubly gated: exact independent DEMO account
identity + explicit local activation. Unknown orders are never retried.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_FLOOR
import hashlib
import json
import math
import os
from pathlib import Path
import time
from typing import Any

from .config import Settings
from .journal import Journal
from .strategy import Signal, decide
from .brain_gate import approval
from .orderflow import BookObserver, BookInsight

ACTIVATION = "YES_I_AUTHORIZE_SENTINEL_DEMO_ONLY"


def floor_volume(requested: float, minimum: float, maximum: float, step: float) -> float:
    values=(requested,minimum,maximum,step)
    if any(not math.isfinite(x) for x in values) or step<=0 or minimum<=0 or maximum<minimum:
        raise ValueError("INVALID_NATIVE_VOLUME_SPEC")
    if requested<minimum:
        return 0.0
    d=lambda x:Decimal(str(x))
    amount=min(d(requested),d(maximum))
    n=((amount-d(minimum))/d(step)).to_integral_value(rounding=ROUND_FLOOR)
    return float(d(minimum)+n*d(step))


def key_for(account: int, signal: Signal) -> str:
    payload=f"Sentinel-v1|{account}|{signal.symbol}|M15|{signal.bar_time}|{signal.family}|{signal.side}"
    return hashlib.sha256(payload.encode()).hexdigest()


def as_bars(rates: Any) -> list[dict]:
    if rates is None:
        return []
    result=[]
    for r in rates:
        try:
            result.append({k:float(r[k]) if k!="time" else int(r[k])
                           for k in ("time","open","high","low","close")})
        except (TypeError,KeyError,ValueError):
            return []
    return sorted(result,key=lambda x:x["time"])


class Trader:
    def __init__(self, settings: Settings, mt5, journal: Journal, *, clock=None):
        self.cfg=settings
        self.mt5=mt5
        self.journal=journal
        self.clock=clock or time.time
        self.account=None
        self.init_done=False
        self.book=BookObserver(mt5,clock=self.clock)

    def connect(self):
        self.cfg.validate()
        if not self.mt5.initialize():
            raise RuntimeError("MT5_TERMINAL_UNAVAILABLE")
        self.init_done=True
        account=self.mt5.account_info()
        terminal=self.mt5.terminal_info()
        if (account is None or terminal is None or not getattr(terminal,"connected",False)
            or int(getattr(account,"trade_mode",-1))!=int(self.mt5.ACCOUNT_TRADE_MODE_DEMO)
            or int(getattr(account,"login",0))!=self.cfg.allowed_login
            or str(getattr(account,"server",""))!=self.cfg.allowed_server
            or int(account.login)==563722 or int(account.login) in self.cfg.blocked_logins):
            self.disconnect()
            raise RuntimeError("SEPARATE_VERIFIED_MT5_DEMO_ACCOUNT_REQUIRED")
        self.account=account
        return account

    def disconnect(self):
        self.book.close()
        if self.init_done:
            self.mt5.shutdown()
        self.init_done=False
        self.account=None

    def enabled(self) -> bool:
        return (self.cfg.mode=="demo_execution" and
                os.environ.get("SENTINEL_ENABLE_DEMO_TRADING")==ACTIVATION)

    def observe(self, symbol: str) -> Signal | None:
        if not self.mt5.symbol_select(symbol,True):
            return None
        m15=as_bars(self.mt5.copy_rates_from_pos(symbol,self.mt5.TIMEFRAME_M15,1,300))
        h1=as_bars(self.mt5.copy_rates_from_pos(symbol,self.mt5.TIMEFRAME_H1,1,120))
        now=self.clock()
        if len(m15)<110 or len(h1)<90 or not m15 or not h1:
            return None
        if m15[-1]["time"]+900>now or h1[-1]["time"]+3600>now:
            return None  # Provider returned an unfinished or future bar.
        if now-(m15[-1]["time"]+900)>1800 or now-(h1[-1]["time"]+3600)>14400:
            return None  # Weekend, closed session, stale history.
        return decide(symbol,m15,h1)

    def _volume(self, symbol: str, side: int, entry: float, stop: float, info, equity: float) -> float:
        otype=self.mt5.ORDER_TYPE_BUY if side==1 else self.mt5.ORDER_TYPE_SELL
        native=self.mt5.order_calc_profit(otype,symbol,1.0,entry,stop)
        if native is None or not math.isfinite(float(native)) or native>=0:
            return 0.0  # Never substitute hard-coded pip/contract values.
        budget=equity*self.cfg.risk_per_trade_pct/100
        loss_per_lot=abs(float(native))
        raw=budget/loss_per_lot
        lots=floor_volume(raw,float(info.volume_min),min(float(info.volume_max),self.cfg.max_lots),float(info.volume_step))
        if lots<=0:
            return 0.0
        checked=self.mt5.order_calc_profit(otype,symbol,lots,entry,stop)
        if checked is None or not math.isfinite(float(checked)) or checked>=0 or abs(float(checked))>budget*1.00001:
            return 0.0
        return lots

    def _request(self, signal: Signal, account, tick, info):
        now=self.clock()
        time_msc=getattr(tick,"time_msc",None)
        quote_time=float(time_msc)/1000 if time_msc is not None else float(getattr(tick,"time",0))
        bid=float(getattr(tick,"bid",0));ask=float(getattr(tick,"ask",0))
        if (not math.isfinite(bid) or not math.isfinite(ask) or bid<=0 or ask<=bid
            or quote_time>now+2 or now-quote_time>self.cfg.max_tick_age_seconds):
            return None,"BAD_OR_STALE_QUOTE"
        spread_bps=(ask-bid)/((ask+bid)/2)*10000
        if spread_bps>self.cfg.max_spread_bps:
            return None,"SPREAD_TOO_WIDE"
        entry=ask if signal.side==1 else bid
        digits=int(info.digits)
        min_stop=float(info.trade_stops_level)*float(info.point)
        stop_distance=max(float(signal.stop_atr)*float(signal.atr),min_stop*1.3)
        if not math.isfinite(stop_distance) or stop_distance<=0:
            return None,"INVALID_STOP_DISTANCE"
        sl=round(entry-signal.side*stop_distance,digits)
        tp=round(entry+signal.side*stop_distance*signal.reward_r,digits)
        # For long, SL/TP are evaluated versus bid; for short versus ask.
        trigger=bid if signal.side==1 else ask
        if signal.side==1 and not (sl<trigger-min_stop and tp>trigger+min_stop):
            return None,"BROKER_STOP_LEVEL_CONFLICT"
        if signal.side==-1 and not (sl>trigger+min_stop and tp<trigger-min_stop):
            return None,"BROKER_STOP_LEVEL_CONFLICT"
        lots=self._volume(signal.symbol,signal.side,entry,sl,info,float(account.equity))
        if lots<=0:
            return None,"NATIVE_RISK_TOO_SMALL_FOR_MIN_LOT"
        # Broker filling_mode is bitmask: 1=FOK, 2=IOC; no guessed fallback.
        filling=int(info.filling_mode)
        if filling&2:
            fill=self.mt5.ORDER_FILLING_IOC
        elif filling&1:
            fill=self.mt5.ORDER_FILLING_FOK
        else:
            return None,"FILLING_MODE_UNSUPPORTED"
        oid=key_for(int(account.login),signal)
        return dict(action=self.mt5.TRADE_ACTION_DEAL,symbol=signal.symbol,
            volume=lots,type=self.mt5.ORDER_TYPE_BUY if signal.side==1 else self.mt5.ORDER_TYPE_SELL,
            price=round(entry,digits),sl=sl,tp=tp,deviation=self.cfg.deviation_points,
            magic=self.cfg.magic,comment="STL-"+oid[:12],type_time=self.mt5.ORDER_TIME_GTC,
            type_filling=fill),"READY"

    def reconcile(self, symbol: str):
        """Confirms an ambiguous order only with broker evidence, else freezes symbol."""
        pending=self.journal.unresolved(self.cfg.allowed_login,symbol)
        if not pending:
            return True
        positions=self.mt5.positions_get()
        if positions is None:
            return False
        try:
            deals=self.mt5.history_deals_get(datetime.fromtimestamp(self.clock(),timezone.utc)-timedelta(days=14),
                                             datetime.fromtimestamp(self.clock(),timezone.utc))
        except Exception:
            deals=None
        for oid,status in pending:
            comment="STL-"+oid[:12]
            found=next((x for x in positions if int(getattr(x,"magic",-1))==self.cfg.magic and
                str(getattr(x,"symbol",""))==symbol and str(getattr(x,"comment",""))==comment),None)
            if found is None and deals is not None:
                found=next((x for x in deals if int(getattr(x,"magic",-1))==self.cfg.magic and
                    str(getattr(x,"symbol",""))==symbol and str(getattr(x,"comment",""))==comment),None)
            if found is not None:
                self.journal.mark(oid,"CONFIRMED","BROKER_POSITION_OR_DEAL_VERIFIED",str(getattr(found,"ticket","")))
        # Fail-closed: explicit negative evidence is not enough to retry an uncertain submission.
        return not self.journal.unresolved(self.cfg.allowed_login,symbol)

    def step(self, symbol: str) -> dict:
        if symbol not in self.cfg.symbols or self.account is None:
            return {"symbol":symbol,"status":"CONFIG_OR_ACCOUNT_NOT_READY"}
        current=self.mt5.account_info()
        terminal=self.mt5.terminal_info()
        if (current is None or terminal is None or not getattr(terminal,"connected",False)
            or int(getattr(current,"login",0))!=self.cfg.allowed_login
            or str(getattr(current,"server",""))!=self.cfg.allowed_server
            or int(getattr(current,"trade_mode",-1))!=int(self.mt5.ACCOUNT_TRADE_MODE_DEMO)):
            return {"symbol":symbol,"status":"DEMO_CONNECTION_LOST"}
        positions=self.mt5.positions_get()
        orders=self.mt5.orders_get()
        if positions is None or orders is None:
            return {"symbol":symbol,"status":"BROKER_STATE_UNAVAILABLE"}
        if any(int(getattr(p,"magic",-1))!=self.cfg.magic for p in positions) or len(orders)>0:
            return {"symbol":symbol,"status":"FOREIGN_POSITION_OR_PENDING_ORDER"}
        if not self.reconcile(symbol):
            return {"symbol":symbol,"status":"UNRESOLVED_BROKER_INTENT"}
        utc_day=datetime.fromtimestamp(self.clock(),timezone.utc).date().isoformat()
        equity=float(current.equity)
        if not math.isfinite(equity) or equity<=0:
            return {"symbol":symbol,"status":"BAD_ACCOUNT_EQUITY"}
        baseline=self.journal.today_start_equity(self.cfg.allowed_login,utc_day,equity)
        if equity<baseline*(1-self.cfg.max_daily_drawdown_pct/100):
            return {"symbol":symbol,"status":"DAILY_DRAWDOWN_LOCK"}
        if len(positions)>=self.cfg.max_positions or any(str(getattr(p,"symbol",""))==symbol for p in positions):
            return {"symbol":symbol,"status":"POSITION_CAP_OR_SYMBOL_BUSY"}
        # DOM is an observation of broker-provided resting orders only.
        # This is deliberately independent of OHLC signals and never triggers orders.
        book=self.book.inspect(symbol) if self.cfg.orderbook_mode!="off" else BookInsight("NOT_REQUESTED")
        details={"symbol":symbol,"orderbook_status":book.status,
                 "book_samples":book.samples,"book_persistent_side":book.persistent_side}
        if book.imbalance is not None:
            details["book_imbalance"]=book.imbalance
        signal=self.observe(symbol)
        if signal is None:
            return {**details,"status":"NO_SIGNAL_OR_STALE_MARKET"}
        if signal.symbol!=symbol or signal.side not in (-1,1) or signal.family not in ("trend_pullback","donchian_breakout"):
            return {**details,"status":"INVALID_STRATEGY_SIGNAL"}
        oid=key_for(self.cfg.allowed_login,signal)
        result={**details,"status":"RESEARCH_SIGNAL","strategy":signal.family,
                "side":"LONG" if signal.side==1 else "SHORT","closed_bar":signal.bar_time,
                "signal_id":oid[:20],"order_submissions":0,"confirmed_fills":0}
        verdict=approval(self.cfg,signal,self.clock())
        result["brain_status"]=verdict.status
        result["research_evidence"]=verdict.evidence
        def finish():
            self.journal.record_decision(oid,self.cfg.allowed_login,symbol,signal.family,
                signal.side,signal.bar_time,verdict.status,book.status,result["status"])
            return result
        if not self.enabled():
            return finish()
        if not verdict.allowed:
            result["status"]="BRAIN_EVIDENCE_NOT_APPROVED"
            return finish()
        signal_age=self.clock()-(signal.bar_time+900)
        if signal_age < 0 or signal_age > self.cfg.max_signal_age_seconds:
            result["status"]="SIGNAL_TOO_OLD_FOR_ENTRY"
            return finish()
        if self.cfg.orderbook_mode=="confirm" and book.persistent_side != signal.side:
            result["status"]="BROKER_DOM_CONFIRMATION_MISSING"
            return finish()
        if (not getattr(terminal,"trade_allowed",False) or not getattr(current,"trade_allowed",False)):
            result["status"]="MT5_TRADING_DISABLED"
            return finish()
        info=self.mt5.symbol_info(symbol)
        tick=self.mt5.symbol_info_tick(symbol)
        if info is None or tick is None or int(getattr(info,"trade_mode",0))!=int(self.mt5.SYMBOL_TRADE_MODE_FULL):
            result["status"]="SYMBOL_NOT_FULLY_TRADABLE"
            return finish()
        request,reason=self._request(signal,current,tick,info)
        if request is None:
            result["status"]=reason
            return finish()
        if not self.journal.reserve(oid,self.cfg.allowed_login,symbol,signal.family,signal.bar_time,signal.side):
            result["status"]="DUPLICATE_SIGNAL_IDEMPOTENT_SKIP"
            return finish()
        try:
            check=self.mt5.order_check(request)
        except Exception:
            self.journal.mark(oid,"PREFLIGHT_REJECTED","ORDER_CHECK_FAILED")
            result["status"]="ORDER_CHECK_FAILED"
            return finish()
        if check is None or int(getattr(check,"retcode",-1))!=0:
            self.journal.mark(oid,"PREFLIGHT_REJECTED","ORDER_CHECK_REJECTED")
            result["status"]="ORDER_CHECK_REJECTED"
            return finish()
        # Confirm account has not switched between observation and submission.
        verification=self.mt5.account_info()
        if (verification is None or int(getattr(verification,"login",0))!=self.cfg.allowed_login or
            str(getattr(verification,"server",""))!=self.cfg.allowed_server or
            int(getattr(verification,"trade_mode",-1))!=int(self.mt5.ACCOUNT_TRADE_MODE_DEMO)):
            self.journal.mark(oid,"NOT_SENT","DEMO_IDENTITY_CHANGED_BEFORE_ORDER")
            result["status"]="DEMO_IDENTITY_CHANGED_BEFORE_ORDER"
            return finish()
        self.journal.mark(oid,"SUBMITTING","INTENT_DURABLE_BEFORE_ORDER_SEND")
        try:
            outcome=self.mt5.order_send(request)
        except Exception:
            # An exception during order_send may mean broker placed the order.
            self.journal.mark(oid,"UNKNOWN","RECONCILIATION_REQUIRED")
            result["status"]="BROKER_OUTCOME_UNKNOWN"
            return finish()
        if outcome is None:
            self.journal.mark(oid,"UNKNOWN","NO_BROKER_RESPONSE")
            result["status"]="BROKER_OUTCOME_UNKNOWN"
            return finish()
        retcode=int(getattr(outcome,"retcode",-1))
        if retcode==int(self.mt5.TRADE_RETCODE_DONE):
            self.journal.mark(oid,"ACKNOWLEDGED","BROKER_ACK_NEEDS_RECONCILIATION",str(getattr(outcome,"order","")))
            result["status"]="BROKER_ACK_AWAITING_RECONCILIATION"
            result["order_submissions"]=1  # Broker acknowledgement is not proof of final fill
        elif retcode in (10006,10007,10014,10015,10016,10018,10019,10021,10030):
            self.journal.mark(oid,"REJECTED","BROKER_EXPLICIT_REJECT_"+str(retcode))
            result["status"]="BROKER_REJECTED"
        else:
            self.journal.mark(oid,"UNKNOWN","AMBIGUOUS_RETCODE_"+str(retcode))
            result["status"]="BROKER_OUTCOME_UNKNOWN"
        return finish()

    def cycle(self) -> dict:
        if self.account is None:
            raise RuntimeError("CONNECT_FIRST")
        states=[]
        for symbol in self.cfg.symbols:
            try:
                states.append(self.step(symbol))
            except Exception as exc:
                states.append({"symbol":symbol,"status":"STEP_EXCEPTION","code":type(exc).__name__})
        output={"service":"SentinelIndependentTrader","mode":self.cfg.mode,
            "execution_armed":self.enabled(),"strategy_policy":self.cfg.strategy_policy,
            "orderbook_mode":self.cfg.orderbook_mode,"account_type":"MT5_DEMO",
            "account_last4":str(self.cfg.allowed_login)[-4:],
            "timestamp":datetime.fromtimestamp(self.clock(),timezone.utc).isoformat(),
            "symbols":states,"not_grok":True,
            "local_decision_records":len(self.journal.recent_decisions(self.cfg.allowed_login,100))}
        path=Path(self.cfg.status_path)
        path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_suffix(".tmp")
        tmp.write_text(json.dumps(output,indent=2,ensure_ascii=False),encoding="utf-8")
        os.replace(tmp,path)
        return output
