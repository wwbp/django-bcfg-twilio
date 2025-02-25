# chat/crud.py
import logging
from .models import User, ChatTranscript
from django.db import transaction

logger = logging.getLogger(__name__)


def verify_update_database(user_id: str, message):
    logger.info(f"Checking database for participant/group ID: {user_id}")
    user, created = User.objects.get_or_create(id=user_id)
    if created:
        logger.info(
            f"Participant/group ID {user_id} not found. Creating a new record.")
        # TODO save metadta from message
    else:
        logger.info(f"Participant/group ID {user_id} exists.")
    return user


def load_chat_history_json(user_id: str):
    logger.info(f"Loading chat history for participant/group ID: {user_id}")
    transcripts = ChatTranscript.objects.filter(
        user_id=user_id).order_by("created_at")
    history = [{"role": t.role, "content": t.content} for t in transcripts]
    return history


@transaction.atomic
def save_chat_round(user_id: str, message, response):
    logger.info(f"Saving chat round for participant/group ID: {user_id}")
    user = User.objects.get(id=user_id)
    ChatTranscript.objects.create(user=user, role="user", content=message)
    ChatTranscript.objects.create(
        user=user, role="assistant", content=response)
    logger.info("Chat round saved successfully.")
