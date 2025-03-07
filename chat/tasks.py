from celery import shared_task, chain
from .send import send_message_to_participant, send_message_to_participant_group
import asyncio
from .ingest import ingest_individual, ingest_group_sync
from config.celery import app
import logging
from celery import shared_task


logger = logging.getLogger(__name__)


@shared_task
def add(x, y):
    return x + y


@app.task
def sample_task():
    print("Celery beat: Running sample task!")
    logger.info("Celery beat: Running sample task!")


@shared_task(bind=True, max_retries=3)
def ingest_individual_task(self, user_id, data):
    """
    Ingest individual chat data, generate a response,
    then chain the sending task.
    """
    try:
        response = ingest_individual(user_id, data)
        # Chain the sending task to ensure proper sequencing
        chain(
            send_message_to_participant_task.s(user_id, response)
        ).apply_async()
        return response
    except Exception as exc:
        logger.error(f"Ingest individual task failed for {user_id}: {exc}")
        raise self.retry(exc=exc, countdown=10)


@shared_task(bind=True, max_retries=3)
def ingest_group_task(self, group_id, data):
    """
    Ingest group chat data, generate a response,
    then chain the group message sending task.
    """
    try:
        response = ingest_group_sync(group_id, data)
        chain(
            send_message_to_participant_group_task.s(group_id, response)
        ).apply_async()
        return response
    except Exception as exc:
        logger.error(f"Ingest group task failed for {group_id}: {exc}")
        raise self.retry(exc=exc, countdown=10)


@shared_task(bind=True, max_retries=3)
def send_message_to_participant_task(self, participant_id, message):
    """
    Sends a message to a single participant.
    Retries on failure with a basic exponential backoff.
    """
    try:
        result = asyncio.run(
            send_message_to_participant(participant_id, message))
        return result
    except Exception as exc:
        logger.error(
            f"Sending message to participant {participant_id} failed: {exc}")
        raise self.retry(exc=exc, countdown=10)


@shared_task(bind=True, max_retries=3)
def send_message_to_participant_group_task(self, group_id, message):
    """
    Sends a message to a participant group.
    Retries on failure with a basic exponential backoff.
    """
    try:
        result = asyncio.run(
            send_message_to_participant_group(group_id, message))
        return result
    except Exception as exc:
        logger.error(f"Sending message to group {group_id} failed: {exc}")
        raise self.retry(exc=exc, countdown=10)
