from celery.schedules import crontab
import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")

# Load configuration from Django settings, using a CELERY_ namespace.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Autodiscover tasks from all installed apps.
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")


# Add a simple beat schedule to run a sample task every minute.
app.conf.beat_schedule = {
    "run-sample-task-every-minute": {
        # Make sure this task is defined in chat/tasks.py
        "task": "chat.tasks.sample_task",
        "schedule": crontab(minute="*/1"),  # Executes every minute
    },
}
