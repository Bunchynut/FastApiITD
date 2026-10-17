from celery import Celery
from celery.schedules import crontab

from src.config import settings

celery_app = Celery(
    'tasks',
    broker=settings.REDIS_URL,
    include=[
        'src.tasks.tasks'
    ]
)

celery_app.conf.beat_schedule = {
    'luboe-nazvanie': {
        'task': 'booking_today_checkin',
        'schedule': 5,
    }

}