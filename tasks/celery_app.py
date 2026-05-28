from celery import Celery
from config import settings

celery_app = Celery(
    "hireflow",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["tasks.matching", "tasks.screening", "tasks.notifications"]
)

celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.broker_connection_retry_on_startup = True