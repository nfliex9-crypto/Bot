"""Celery tasks for 24/7 trading."""
from app.worker.celery_app import celery_app
from app.engine import TradingEngine


@celery_app.task(name="app.worker.tasks.run_trading_cycle")
def run_trading_cycle():
    """Run one trading cycle - called by Celery Beat every 5 min."""
    engine = TradingEngine()
    return engine.run_cycle()
