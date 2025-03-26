from celery import shared_task
from config.celery import app
import logging


logger = logging.getLogger(__name__)


@shared_task
def add(x, y):
    return x + y


@app.task
def sample_task():
    print("Celery beat: Running sample task!")
    logger.info("Celery beat: Running sample task!")
