"""Celery app and tasks."""
from celery import Celery
from celery.schedules import crontab
from config import settings

celery_app = Celery(
    "trading_bot",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "run-trading-cycle": {
            "task": "app.worker.tasks.run_trading_cycle",
            "schedule": crontab(minute="*/5"),  # Every 5 minutes
        },
    },
)
