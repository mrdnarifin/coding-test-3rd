from celery import Celery
from app.core.config import settings
# Set up Celery
celery_app = Celery('document_processing', broker=settings.REDIS_URL)

celery_app.conf.update(
    result_backend=settings.REDIS_URL,
    task_serializer='json',
    accept_content=['json'],
    timezone='UTC',
    enable_utc=True
)

celery_app.conf.update(
    imports=["app.tasks.document_processing"]
)
