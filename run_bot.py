#!/usr/bin/env python3
"""
Run the trading bot - API server + optional background worker.
Usage:
  python run_bot.py              # API only
  python run_bot.py --worker     # Celery worker
  python run_bot.py --beat       # Celery beat
  python run_bot.py --standalone # Run cycle in loop (no Docker/Celery)
"""
import argparse
import time
from config import settings

from app.database.session import init_db
from app.engine import TradingEngine


def run_standalone():
    """Run trading cycles in a loop (for simple deployment without Redis)."""
    init_db()
    engine = TradingEngine()
    print(f"Running in {settings.TRADING_MODE} mode. Cycle every 5 min. Ctrl+C to stop.")
    while True:
        try:
            results = engine.run_cycle()
            print(f"Cycle: {results}")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(300)  # 5 min


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true", help="Run Celery worker")
    parser.add_argument("--beat", action="store_true", help="Run Celery beat")
    parser.add_argument("--standalone", action="store_true", help="Run cycles in loop (no Redis)")
    args = parser.parse_args()

    if args.worker:
        from app.worker.celery_app import celery_app
        celery_app.worker_main(argv=["worker", "--loglevel=info"])
    elif args.beat:
        from app.worker.celery_app import celery_app
        celery_app.worker_main(argv=["beat", "--loglevel=info"])
    elif args.standalone:
        run_standalone()
    else:
        import uvicorn
        uvicorn.run("app.main:app", host=settings.API_HOST, port=settings.API_PORT)


if __name__ == "__main__":
    main()
