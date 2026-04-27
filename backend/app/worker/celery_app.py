from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "paytopay",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    beat_schedule={
        "retry-stuck-payouts": {
            "task": "app.worker.tasks.retry_stuck_payouts",
            "schedule": 10.0,
        },
    },
)
