from celery import Celery

from app.config import settings

celery_app = Celery(
    "pmbi",
    broker=settings.celery_broker_url,
    backend=settings.redis_url,
    include=["app.tasks.analytics_tasks", "app.tasks.ml_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
