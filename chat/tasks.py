from .send import send_message_to_participant, send_message_to_participant_group
import asyncio
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
def ingest_individual_task(user_id, data):
    response = ingest_individual(user_id, data)
    send_message_to_participant_task.delay(user_id, response)
    return response


@shared_task
def ingest_group_task(group_id, data):
    response = ingest_group_sync(group_id, data)
    send_message_to_participant_group_task.delay(group_id, response)
    return response


@shared_task
def send_message_to_participant_task(participant_id, message):
    result = asyncio.run(send_message_to_participant(participant_id, message))
    return result


@shared_task
def send_message_to_participant_group_task(group_id, message):
    result = asyncio.run(send_message_to_participant_group(group_id, message))
    return result
