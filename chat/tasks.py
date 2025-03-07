from .ingest import ingest_individual, ingest_group_sync
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


@shared_task
def ingest_individual_task(participant_id, data):
    ingest_individual(participant_id, data)


@shared_task
def ingest_group_task(group_id, data):
    ingest_group_sync(group_id, data)
