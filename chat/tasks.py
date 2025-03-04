from config.celery import app
import logging
from celery import shared_task


@shared_task
def add(x, y):
    return x + y


logger = logging.getLogger(__name__)


@app.task
def sample_task():
    print("Celery beat: Running sample task!")
    logger.info("Celery beat: Running sample task!")
