"""Windows entrypoint. Default research mode, never deploys or starts itself."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
import time
from .config import Settings
from .journal import Journal
from .trader import Trader, ACTIVATION


def single_instance(lock_path: Path):
    if os.name!="nt":
        raise RuntimeError("WINDOWS_MT5_TERMINAL_REQUIRED")
    import msvcrt
    lock_path.parent.mkdir(parents=True,exist_ok=True)
    file=lock_path.open("a+b")
    file.seek(0);file.write(b"0");file.flush();file.seek(0)
    try:
        msvcrt.locking(file.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:
        file.close()
        raise RuntimeError("SENTINEL_TRADER_ALREADY_RUNNING")
    return file


def main():
    parser=argparse.ArgumentParser(description="Independent MT5 DEMO-only Sentinel trader")
    parser.add_argument("--config",required=True)
    parser.add_argument("--once",action="store_true")
    args=parser.parse_args()
    cfg=Settings.from_file(args.config)
    if cfg.mode=="demo_execution" and os.environ.get("SENTINEL_ENABLE_DEMO_TRADING")!=ACTIVATION:
        raise RuntimeError("EXPLICIT_LOCAL_DEMO_EXECUTION_FLAG_REQUIRED")
    import MetaTrader5 as mt5
    lock=single_instance(Path(cfg.journal_path).with_suffix(".lock"))
    journal=Journal(cfg.journal_path)
    service=Trader(cfg,mt5,journal)
    try:
        service.connect()
        while True:
            status=service.cycle()
            print(json.dumps(status,ensure_ascii=False),flush=True)
            if os.environ.get("SENTINEL_TRADER_REPORT_STATUS")=="1":
                try:
                    from .telemetry import upload
                    upload(status)
                except Exception as exc:
                    print("Sentinel status telemetry unavailable:",type(exc).__name__,flush=True)
            if args.once:
                break
            time.sleep(cfg.poll_seconds)
    finally:
        service.disconnect()
        journal.close()
        lock.close()

if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        print("Sentinel trader halted:",type(exc).__name__,str(exc)[:180],file=sys.stderr)
        sys.exit(1)
