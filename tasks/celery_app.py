from celery import Celery
from config import settings

celery_app = Celery(
    "transcriber",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["tasks.process_meeting"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 60 minutes for long recordings
    worker_prefetch_multiplier=1,
    result_expires=3600,
)
