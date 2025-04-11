from django.utils import timezone
import re
import json
import logging

from .constant import MODERATION_MESSAGE_DEFAULT
from ..models import (
    Group,
    GroupChatTranscript,
    IndividualSession,
    TranscriptRole,
    User,
    ChatTranscript,
    Prompt,
    Control,
)
from django.db import transaction

logger = logging.getLogger(__name__)


def ingest_request(participant_id: str, data: dict):
    """
    Ingests an individual request by either creating a new user record or updating
    an existing one. The operation is wrapped in an atomic transaction for consistency.
    """
    logger.info("Processing request for participant ID: %s", participant_id)
    context: dict = data.get("context", {})
    message: str = data.get("message", "")

    with transaction.atomic():
        # Provide a default for created_at to avoid null value issues.
        user, _ = User.objects.update_or_create(
            id=participant_id,
            defaults={
                "created_at": timezone.now(),
                "school_name": context.get("school_name", ""),
                "school_mascot": context.get("school_mascot", ""),
                "name": context.get("name", ""),
            },
        )
        session, created_session = IndividualSession.objects.get_or_create(
            user=user,
            week_number=context.get("week_number"),
            message_type=context.get("message_type"),
        )

        if created_session:
            # if we created a new session, we need to add the initial message to it
            ChatTranscript.objects.create(
                session=session, role=TranscriptRole.ASSISTANT, content=context.get("initial_message")
            )

        # in either case, we need to add the user message to the transcript
        ChatTranscript.objects.create(session=session, role=TranscriptRole.USER, content=message)

    return user


def validate_ingest_group_request(group_id: str, data: dict):
    logger.info(f"Checking database for group ID: {group_id}")
    group, created = Group.objects.get_or_create(id=group_id)
    context = data.get("context", {})
    message = data.get("message", "")
    sender_id = data.get("sender_id")

    if created:
        logger.info(f"Group ID {group_id} not found. Creating a new record.")
        group.initial_message = context.get("initial_message", "")
        group.week_number = context.get("week_number")
        group.save()

        # Create the initial assistant transcript entry (sender remains null)
        GroupChatTranscript.objects.create(group=group, role=TranscriptRole.ASSISTANT, content=group.initial_message)

        # Create and add participants to the group
        for participant in context.get("participants", []):
            user, user_created = User.objects.get_or_create(id=participant["id"])
            if user_created:
                user.name = participant.get("name", "")
                user.school_name = context.get("school_name", "")
                user.school_mascot = context.get("school_mascot", "")
                user.save()
            group.users.add(user)

        # Now add the incoming user message transcript entry with sender info.
        # assume a sender_id is provided in data.
        sender = None
        if sender_id:
            sender, _ = User.objects.get_or_create(id=sender_id)

        GroupChatTranscript.objects.create(group=group, role=TranscriptRole.USER, content=message, sender=sender)
    else:
        logger.info(f"Group ID {group_id} exists.")
        updated = False

        # Check if week_number has changed and update if needed.
        new_week = context.get("week_number")
        if new_week is not None and new_week != group.week_number:
            logger.info(f"Week number changed for group {group_id} from {group.week_number} to {new_week}.")
            group.week_number = new_week
            updated = True

        # Check if the initial message has changed and update transcript accordingly.
        new_initial_message = context.get("initial_message")
        if new_initial_message and new_initial_message != group.initial_message:
            logger.info(f"Initial message changed for group {group_id}. Updating transcript.")
            group.initial_message = new_initial_message
            GroupChatTranscript.objects.create(group=group, role=TranscriptRole.ASSISTANT, content=new_initial_message)
            updated = True

        # Update or add new participants before saving the user message transcript.
        for participant in context.get("participants", []):
            user, user_created = User.objects.get_or_create(id=participant["id"])
            if user_created:
                user.name = participant.get("name", "")
                user.school_name = context.get("school_name", "")
                user.school_mascot = context.get("school_mascot", "")
                user.save()
            group.users.add(user)

        # Now add the incoming user message transcript with the sender field.
        sender_id = data.get("sender_id")
        sender = None
        if sender_id:
            sender, _ = User.objects.get_or_create(id=sender_id)
        GroupChatTranscript.objects.create(group=group, role=TranscriptRole.USER, content=message, sender=sender)

        if updated:
            group.save()

    return group


def sanitize_name(name: str) -> str:
    """
    Remove any characters that are not letters, digits, underscores, or hyphens.
    If the sanitized name is empty, return a default value.
    """
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "", name)
    return sanitized if sanitized else "default"


def load_individual_chat_history(user: User):
    logger.info(f"Loading chat history for participant: {user.id}")

    # Retrieve all transcripts in chronological order
    transcripts = ChatTranscript.objects.filter(session__user_id=user.id).order_by("created_at")

    # Get the most recent user transcript
    latest_user_transcript = (
        ChatTranscript.objects.filter(session__user_id=user.id, role=TranscriptRole.USER)
        .order_by("-created_at")
        .first()
    )

    # Build chat history, excluding the latest user message
    history = []
    for t in transcripts:
        if latest_user_transcript and t.id == latest_user_transcript.id:
            continue

        if t.role == TranscriptRole.USER:
            sender_name = t.session.user.name if t.session.user.name else TranscriptRole.USER
        else:  # role is assistant
            sender_name = t.session.user.school_mascot if t.session.user.school_mascot else TranscriptRole.ASSISTANT

        sender_name = sanitize_name(sender_name)
        history.append(
            {
                "role": t.role,
                "content": t.content,
                "name": sender_name,
            }
        )

    # Extract only the message content for the latest user message
    latest_user_message_content = latest_user_transcript.content if latest_user_transcript else ""

    return history, latest_user_message_content


def load_detailed_transcript(group_id: str):
    logger.info(f"Loading detailed transcript for group ID: {group_id}")
    transcripts = GroupChatTranscript.objects.filter(group_id=group_id).order_by("created_at")
    messages = []
    for t in transcripts:
        sender_name = t.sender.name if t.sender else TranscriptRole.ASSISTANT  # TODO: pipe mascot name
        messages.append({"sender": sender_name, "role": t.role, "timestamp": str(t.created_at), "content": t.content})
    return json.dumps(messages, indent=2)


def load_chat_history_json_group(group_id: str):
    logger.info(f"Loading chat history for group ID: {group_id}")
    transcripts = GroupChatTranscript.objects.filter(group_id=group_id).order_by("created_at")
    history = [{"role": t.role, "content": t.content} for t in transcripts]
    return history


def get_latest_assistant_response(user_id: str):
    logger.info(f"Fetching latest assistant response for participant with id: {user_id}")

    # Retrieve the most recent assistant response for the given user
    latest_assistant_transcript = (
        ChatTranscript.objects.filter(session__user_id=user_id, role=TranscriptRole.ASSISTANT)
        .order_by("-created_at")
        .first()
    )

    # Return the content if a transcript exists; otherwise, return None
    return latest_assistant_transcript.content if latest_assistant_transcript else None


def save_assistant_response(user: User, response):
    logger.info(f"Saving assistant response for participant: {user.id}")
    ChatTranscript.objects.create(session=user.current_session, role=TranscriptRole.ASSISTANT, content=response)
    logger.info("Assistant Response saved successfully.")


@transaction.atomic
def save_chat_round_group(group_id: str, sender_id: str, message, response):
    logger.info(f"Saving chat round for group ID: {group_id}")
    group = Group.objects.get(id=group_id)
    if message:
        sender = User.objects.get(id=sender_id)
        GroupChatTranscript.objects.create(group=group, role=TranscriptRole.USER, content=message, sender=sender)
    if response:
        GroupChatTranscript.objects.create(group=group, role=TranscriptRole.ASSISTANT, content=response)
    logger.info("Chat round saved successfully.")


INSTRUCTION_PROMPT_TEMPLATE = (
    "Using the below system prompt as your guide, engage with the user in a "
    "manner that reflects your assigned persona and follows the activity instructions"
    "System Prompt: {system}\n\n"
    "Assigned Persona: {persona}\n\n"
    "Assistant Name: {assistant_name}\n\n"
    "Activity: {activity}\n\n"
)


def load_instruction_prompt(user: User):
    # get latest session for the user
    session = user.sessions.order_by("-created_at").first()
    week = session.week_number
    message_type = session.message_type
    assistant_name = user.school_mascot if user.school_mascot else "Assistant"

    # Load the most recent controls record
    controls = Control.objects.latest("created_at")
    # Retrieve the prompt for the given week, falling back to a default if none is found
    prompt_obj = None
    if week is not None and message_type is not None:
        prompt_obj = Prompt.objects.filter(week=week, type=message_type).order_by("created_at").last()

    if prompt_obj:
        activity = prompt_obj.activity
    else:
        logger.info(f"No Prompt found for week '{week}' and type '{message_type}'. Falling back to default activity.")
        raise ValueError(f"No Prompt found for week '{week}' and type '{message_type}'.")

    # Format the final prompt using the template
    instruction_prompt = INSTRUCTION_PROMPT_TEMPLATE.format(
        system=controls.system,
        persona=controls.persona,
        assistant_name=assistant_name,
        activity=activity,
    )
    return instruction_prompt


def get_moderation_message():
    try:
        controls = Control.objects.latest("created_at")
    except Control.DoesNotExist:
        controls = Control.objects.create()
    if len(controls.moderation) > 0:
        return controls.moderation
    return MODERATION_MESSAGE_DEFAULT
