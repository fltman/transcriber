import sys
from pathlib import Path

# Ensure project root is on sys.path so lazy imports (model_config, etc.) work
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from celery import Celery
from config import settings

celery_app = Celery(
    "transcriber",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["tasks.process_meeting", "tasks.polish_task", "tasks.finalize_task", "tasks.action_task"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_soft_time_limit=3300,  # 55 min soft limit (raises SoftTimeLimitExceeded)
    task_time_limit=3600,       # 60 min hard kill
    worker_prefetch_multiplier=1,
    result_expires=3600,
    worker_redirect_stdouts_level="INFO",
)
