#!/usr/bin/env python3
"""
Sentinel MT5 Windows Agent (DEMO-ONLY).
No account password or orders are sent to the dashboard.
Windows MetaTrader terminal must already be logged into the desired demo account.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import pathlib
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from logging.handlers import RotatingFileHandler

HOME = pathlib.Path(os.environ.get("LOCALAPPDATA", pathlib.Path.home())) / "SentinelMT5"
CONFIG_PATH = HOME / "config.json"
LOCK_PATH = HOME / "agent.lock"
SERVICE = "SentinelMT5"
HEARTBEAT_SECS = 20
STOP = False

def log_init() -> None:
    HOME.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler = RotatingFileHandler(HOME / "agent.log", maxBytes=2_000_000, backupCount=4, encoding="utf-8")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    logger.addHandler(stream)

def request_json(url: str, action: str, payload: dict | None = None,
                 agent_id: str = "", agent_token: str = "", bypass: str = "") -> dict:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("Agent endpoint must be a valid HTTPS URL")
    endpoint = url.rstrip("/") + "/api/mt5?action=" + urllib.parse.quote(action, safe="")
    headers = {"Accept": "application/json", "Content-Type": "application/json", "User-Agent":"SentinelMT5-Agent/1.0"}
    if agent_id and agent_token:
        headers["x-mt5-agent-id"] = agent_id
        headers["x-mt5-agent-token"] = agent_token
    if bypass:
        headers["x-vercel-protection-bypass"] = bypass
    req = urllib.request.Request(endpoint, data=json.dumps(payload or {}).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            result = json.loads(response.read(10240))
            if not result.get("ok"):
                raise RuntimeError(result.get("error", "Unexpected bridge response"))
            return result
    except urllib.error.HTTPError as exc:
        description = exc.code
        try:
            description = json.loads(exc.read(2048)).get("error", exc.code)
        except Exception:
            pass
        raise RuntimeError(f"Bridge returned {description}") from exc

def read_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError("Not paired. Run: py agent.py pair --url ... --code ...") from exc

def save_config(data: dict) -> None:
    HOME.mkdir(parents=True, exist_ok=True)
    file_tmp = CONFIG_PATH.with_suffix(".tmp")
    file_tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    file_tmp.replace(CONFIG_PATH)
    # Secure Windows ACL: currently logged-in user + SYSTEM.
    if os.name == "nt":
        user = os.environ.get("USERNAME", "")
        if user:
            subprocess.run(["icacls", str(CONFIG_PATH), "/inheritance:r",
                            "/grant:r", f"{user}:(R,W)", "SYSTEM:(F)"],
                           capture_output=True, check=False)

def keyring_store(agent_id: str, token: str) -> None:
    try:
        import keyring
    except ImportError as exc:
        raise RuntimeError("Missing keyring: py -m pip install keyring") from exc
    keyring.set_password(SERVICE, agent_id, token)

def keyring_load(agent_id: str) -> str:
    try:
        import keyring
    except ImportError as exc:
        raise RuntimeError("Missing keyring module") from exc
    token = keyring.get_password(SERVICE, agent_id)
    if not token:
        raise RuntimeError("Agent token not found in Windows Credential Manager; re-pair required")
    return token

def pair(args) -> None:
    if os.name != "nt":
        raise RuntimeError("Pairing is intended for Windows. MT5 terminal runs on Windows.")
    if not args.code:
        raise RuntimeError("Pairing code required")
    result = request_json(args.url, "claim",
                          {"code": args.code, "agent_name": args.name}, bypass=args.bypass or "")
    agent_id,token = result["agent_id"],result["agent_token"]
    keyring_store(agent_id,token)
    if args.bypass:
        keyring_store("vercel-bypass:" + agent_id, args.bypass)
    previous = {}
    try:
        previous = read_config()
    except RuntimeError:
        pass
    config = {
        "console_url": args.url.rstrip("/"),
        "agent_id": agent_id,
        "agent_name": args.name,
        "mt5_path": args.mt5_path or previous.get("mt5_path",""),
        "bot_command": previous.get("bot_command",[]),
        "auto_restart_bot": previous.get("auto_restart_bot",False),
    }
    save_config(config)
    print("Paired successfully. ID:",agent_id)
    print("Token stored in Windows Credential Manager; no MT5 password was shared.")
    print("Run: py agent.py run")
    print("Install auto-start: powershell -ExecutionPolicy Bypass -File .\\install_agent.ps1")

class MT5Monitor:
    def __init__(self, mt5_path: str = ""):
        self.mt5_path = mt5_path
        self.module = None
        self.initialized = False
        self.retry_at = 0.0
        self.fail_count = 0
    def disconnect(self):
        if self.initialized and self.module is not None:
            try:
                self.module.shutdown()
            except Exception:
                pass
        self.initialized = False
    def read(self) -> dict:
        empty = {
            "connection_state": "disconnected", "trade_mode":"unknown",
            "account_last4": None, "broker_server":"","account_currency":"",
            "balance":None, "equity":None, "open_positions":None,
            "terminal_version":"", "last_error":""
        }
        try:
            if self.module is None:
                import MetaTrader5 as mt5
                self.module = mt5
            mt5=self.module
            if not self.initialized:
                if time.monotonic()<self.retry_at:
                    empty["last_error"]="Waiting for next MT5 retry"
                    return empty
                ok = mt5.initialize(self.mt5_path) if self.mt5_path else mt5.initialize()
                if not ok:
                    self.fail_count+=1
                    self.retry_at=time.monotonic()+min(120,5*(2**min(self.fail_count,5)))
                    empty["last_error"]="MT5 initialize failed: "+str(mt5.last_error())[:180]
                    return empty
                self.initialized=True
                self.fail_count=0
            terminal=mt5.terminal_info()
            account=mt5.account_info()
            if terminal is None or account is None or not getattr(terminal,"connected",False):
                self.disconnect()
                empty["last_error"]="Terminal not connected to broker"
                return empty
            if int(account.trade_mode)!=int(mt5.ACCOUNT_TRADE_MODE_DEMO):
                self.disconnect()
                empty["last_error"]="Real/contest account rejected. Switch MT5 to DEMO and retry."
                return empty
            positions=mt5.positions_get()
            if positions is None:
                self.disconnect()
                empty["last_error"]="Could not read demo positions"
                return empty
            version=mt5.version()
            return {
                "connection_state":"connected",
                "trade_mode":"demo",
                "account_last4":str(account.login)[-4:],
                "broker_server":str(account.server)[:80],
                "account_currency":str(account.currency)[:8],
                "balance":float(account.balance),"equity":float(account.equity),
                "open_positions":len(positions),
                "terminal_version":".".join(map(str,version[:3])) if version else "",
                "last_error":""
            }
        except Exception as exc:
            self.disconnect()
            empty["last_error"]=f"{type(exc).__name__}: {str(exc)[:140]}"
            return empty

class BotSupervisor:
    """Optional *locally configured* bot command. Never accepts commands from the web."""
    def __init__(self, command, enabled):
        self.command=command if isinstance(command,list) and all(isinstance(x,str) for x in command) else []
        self.enabled=bool(enabled) and bool(self.command)
        self.proc=None
        self.crashes=0
        self.next_restart=0.0
        self.last_start=0.0
    def tick(self, demo_connected: bool)->str:
        if not self.enabled:return "unconfigured"
        if not demo_connected:
            # Stop a bot started under this supervisor if the account ceases to be DEMO.
            if self.proc is not None and self.proc.poll() is None:
                self.stop()
            return "stopped"
        if self.proc is not None and self.proc.poll() is None:
            if time.monotonic()-self.last_start>600:self.crashes=0
            return "running"
        if time.monotonic()<self.next_restart:return "restarting"
        if self.proc is not None:
            # Child exited unexpectedly: exponential backoff prevents rapid crash loops.
            self.crashes += 1
            self.next_restart = time.monotonic() + min(300, 5 * (2 ** min(self.crashes, 6)))
            self.proc = None
            logging.warning("Managed demo bot exited; retry scheduled in %.0fs", self.next_restart-time.monotonic())
            return "restarting"
        try:
            kwargs={"cwd":str(pathlib.Path(self.command[0]).parent)} if pathlib.Path(self.command[0]).is_absolute() else {}
            env=os.environ.copy()
            env.update({"TRADING_MODE":"demo","SENTINEL_DEMO_ONLY":"1"})
            self.proc=subprocess.Popen(self.command,env=env,stdin=subprocess.DEVNULL,
                                       creationflags=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0),**kwargs)
            self.last_start=time.monotonic()
            logging.info("Locally configured DEMO bot started. pid=%s",self.proc.pid)
            return "running"
        except Exception as exc:
            self.crashes+=1
            self.next_restart=time.monotonic()+min(300,5*2**min(self.crashes,6))
            logging.error("Bot start failed: %s",exc)
            return "failed"
    def stop(self):
        if self.proc is None:return
        if self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=12)
            except Exception:
                try:self.proc.kill()
                except Exception:pass
        self.proc=None

def single_instance():
    import msvcrt
    f=LOCK_PATH.open("a+b")
    f.seek(0)
    f.write(b"0")
    f.flush()
    f.seek(0)
    try:msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:raise RuntimeError("Another Sentinel agent instance is already running")
    return f

def run(args) -> None:
    if os.name!="nt":raise RuntimeError("This MT5 agent needs Windows")
    lock=single_instance()
    cfg=read_config()
    token=keyring_load(cfg["agent_id"])
    bypass = ""
    try:
        bypass = keyring_load("vercel-bypass:" + cfg["agent_id"])
    except RuntimeError:
        if cfg.get("vercel_bypass"):
            bypass = cfg["vercel_bypass"]
            keyring_store("vercel-bypass:" + cfg["agent_id"], bypass)
            cfg.pop("vercel_bypass", None)
            save_config(cfg)
    m=MT5Monitor(cfg.get("mt5_path",""))
    supervisor=BotSupervisor(cfg.get("bot_command",[]),cfg.get("auto_restart_bot",False))
    global STOP
    def shutdown_handler(signum,frame):
        global STOP
        STOP=True
    signal.signal(signal.SIGTERM,shutdown_handler)
    signal.signal(signal.SIGINT,shutdown_handler)
    logging.info("Sentinel agent started, awaiting demo account. Agent id=%s",cfg["agent_id"])
    while not STOP:
        start=time.monotonic()
        state=m.read()
        state["bot_state"]=supervisor.tick(state.get("trade_mode")=="demo" and state.get("connection_state")=="connected")
        try:
            request_json(cfg["console_url"],"heartbeat",state,
                         agent_id=cfg["agent_id"],agent_token=token,bypass=bypass)
            logging.info("Heartbeat sent. MT5=%s bot=%s",state["connection_state"],state["bot_state"])
        except Exception as exc:
            logging.warning("Heartbeat upload failed: %s",exc)
            if "DEVICE_REVOKED_OR_NOT_FOUND" in str(exc):
                logging.error("Device revoked. Agent exiting.");break
        elapsed=time.monotonic()-start
        # deliberate looping allows safe shutdown.
        until=time.monotonic()+max(1,HEARTBEAT_SECS-elapsed)
        while not STOP and time.monotonic()<until:time.sleep(min(1,until-time.monotonic()))
    supervisor.stop()
    m.disconnect()
    lock.close()
    logging.info("Sentinel agent stopped")

def main() -> None:
    log_init()
    parser=argparse.ArgumentParser(description="Sentinel MT5 DEMO-only monitoring agent")
    sub=parser.add_subparsers(dest="operation",required=True)
    p=sub.add_parser("pair",help="Claim a one-time code from the Sentinel dashboard")
    p.add_argument("--url",required=True,help="Public HTTPS console origin")
    p.add_argument("--code",required=True,help="20-character pairing code")
    p.add_argument("--name",default=os.environ.get("COMPUTERNAME","Windows MT5 Agent"))
    p.add_argument("--mt5-path",default="",help="Optional terminal64.exe absolute path")
    p.add_argument("--bypass",default="",help="Vercel deployment-protection bypass if configured")
    sub.add_parser("run",help="Run continuous heartbeats, reconnection and bot supervision")
    args=parser.parse_args()
    try:pair(args) if args.operation=="pair" else run(args)
    except Exception as exc:
        logging.error("%s: %s",type(exc).__name__,str(exc))
        sys.exit(1)

if __name__=="__main__":
    main()
