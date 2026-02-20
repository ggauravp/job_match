from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# set default Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('core')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

from celery.schedules import crontab

app.conf.beat_schedule = {
    'crawl-jobs-every-day-8pm': {
        'task': 'main.tasks.run_all_crawlers',
        'schedule': crontab(hour=20, minute=0),
    },
}