# chat/crud.py
import logging

from .constant import MODERATION_MESSAGE_DEFAULT
from .models import Group, GroupChatTranscript, User, ChatTranscript, Prompt, Control
from django.db import transaction

logger = logging.getLogger(__name__)


def verify_update_database(user_id: str, data: dict):
    logger.info(f"Checking database for participant/group ID: {user_id}")
    user, created = User.objects.get_or_create(id=user_id)
    if created:
        logger.info(
            f"Participant/group ID {user_id} not found. Creating a new record.")
        user.school_name = data["context"]["school_name"]
        user.school_mascot = data["context"]["school_mascot"]
        user.name = data["context"]["name"]
        user.initial_message = data["context"]["initial_message"]
        user.save()
        ChatTranscript.objects.create(
            user=user, role="assistant", content=data["context"]["initial_message"])
    else:
        logger.info(f"Participant/group ID {user_id} exists.")
    return user


def verify_update_database_group(group_id: str, data: dict):
    logger.info(f"Checking database for group ID: {group_id}")
    group, group_created = Group.objects.get_or_create(id=group_id)
    if group_created:
        logger.info(f"Group ID {group_id} not found. Creating a new record.")
        group.initial_message = data["context"]["initial_message"]
        group.save()
        for participant in data["context"].get("participants", []):
            user, user_created = User.objects.get_or_create(
                id=participant["id"])
            if user_created:
                user.name = participant.get("name", user.name)
                user.school_name = data["context"]["school_name"]
                user.school_mascot = data["context"]["school_mascot"]
                user.save()
            group.users.add(user)
        GroupChatTranscript.objects.create(
            group=group, role="assistant", content=data["context"]["initial_message"])
    else:
        logger.info(f"Group ID {group_id} exists.")
    return group


def load_chat_history_json(user_id: str):
    logger.info(f"Loading chat history for participant/group ID: {user_id}")
    transcripts = ChatTranscript.objects.filter(
        user_id=user_id).order_by("created_at")
    history = [{"role": t.role, "content": t.content} for t in transcripts]
    return history


def load_detailed_transcript(group_id: str):
    logger.info(f"Loading detailed transcript for group ID: {group_id}")
    transcripts = GroupChatTranscript.objects.filter(
        group_id=group_id).order_by("created_at")
    transcript_text = "<|sender name; role; timestamp; content|>"
    for t in transcripts:
        sender_name = t.sender.name if t.sender else "assistant" # TODO pipe mascot name
        transcript_text += f"<|{sender_name};{t.role};{t.created_at};{t.content}|>"
    return transcript_text


def load_chat_history_json_group(group_id: str):
    logger.info(f"Loading chat history for group ID: {group_id}")
    transcripts = GroupChatTranscript.objects.filter(
        group_id=group_id).order_by("created_at")
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


@transaction.atomic
def save_chat_round_group(group_id: str, sender_id: str, message, response):
    logger.info(f"Saving chat round for group ID: {group_id}")
    group = Group.objects.get(id=group_id)
    if message:
        sender = User.objects.get(id=sender_id)
        GroupChatTranscript.objects.create(
            group=group, role="user", content=message, sender=sender)
    if response:
        GroupChatTranscript.objects.create(
            group=group, role="assistant", content=response)
    logger.info("Chat round saved successfully.")


def load_chat_prompt(week: int, group=False):
    try:
        controls = Control.objects.latest('created_at')
    except Control.DoesNotExist:
        controls = Control.objects.create()
    prompt = Prompt.objects.filter(week=week).last()
    activity = prompt.activity if prompt else controls.default
    prompt = f"System Prompt: {controls.system} \n AI BOT Persona: {controls.persona} \n Week's Activity: {activity}"
    return prompt


def get_moderation_message():
    try:
        controls = Control.objects.latest('created_at')
    except Control.DoesNotExist:
        controls = Control.objects.create()
    if len(controls.moderation) > 0:
        return controls.moderation
    return MODERATION_MESSAGE_DEFAULT
