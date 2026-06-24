"""
Celery configuration for Attendrix
"""
import os
from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendrix.settings')

app = Celery('attendrix')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Configure Celery beat schedule
app.conf.beat_schedule = {
    # Attendance analytics calculation
    'calculate-daily-analytics': {
        'task': 'apps.analytics.tasks.calculate_daily_attendance_analytics',
        'schedule': 60.0 * 60.0,  # Every hour
    },
    # Send attendance alerts
    'send-attendance-alerts': {
        'task': 'apps.alerts.tasks.send_attendance_alerts',
        'schedule': 60.0 * 30.0,  # Every 30 minutes
    },
    # Clean up expired sessions
    'cleanup-expired-sessions': {
        'task': 'apps.authentication.tasks.cleanup_expired_sessions',
        'schedule': 60.0 * 60.0 * 6,  # Every 6 hours
    },
    # Generate predictive analytics
    'generate-predictive-analytics': {
        'task': 'apps.analytics.tasks.generate_predictive_analytics',
        'schedule': 60.0 * 60.0 * 24,  # Daily
    },
    # Sync external systems
    'sync-external-systems': {
        'task': 'apps.api.tasks.sync_external_systems',
        'schedule': 60.0 * 60.0 * 2,  # Every 2 hours
    },
}

# Task configuration
app.conf.task_serializer = 'json'
app.conf.result_serializer = 'json'
app.conf.accept_content = ['json']
app.conf.result_expires = 60 * 60 * 24  # 24 hours
app.conf.timezone = 'UTC'
app.conf.enable_utc = True

# Error handling
app.conf.task_reject_on_worker_lost = True
app.conf.task_acks_late = True
app.conf.worker_prefetch_multiplier = 1

@app.task(bind=True)
def debug_task(self):
    """Debug task to test Celery"""
    print(f'Request: {self.request!r}')
