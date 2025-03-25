from django.utils import timezone
import re
import json
import logging

from .constant import MODERATION_MESSAGE_DEFAULT
from .models import Group, GroupChatTranscript, User, ChatTranscript, Prompt, Control
from django.db import transaction

logger = logging.getLogger(__name__)


def is_test_user(participant_id: str):
    try:
        user = User.objects.get(id=participant_id)
        return user.is_test
    except User.DoesNotExist:
        return False


def is_test_group(group_id: str):
    try:
        group = Group.objects.get(id=group_id)
        return group.is_test
    except Group.DoesNotExist:
        return False


def create_new_user(user, context: dict, message: str):
    """
    Populate a newly created user instance with context data and create the
    initial chat transcripts.
    """
    try:
        # Update the new user instance with provided context data
        user.school_name = context.get("school_name", "")
        user.school_mascot = context.get("school_mascot", "")
        user.name = context.get("name", "")
        user.initial_message = context.get("initial_message", "")
        user.week_number = context.get("week_number")
        user.save()  # Save updated fields

        # Create initial transcripts:
        # 1. Assistant transcript with the initial message.
        ChatTranscript.objects.create(
            user=user,
            role="assistant",
            content=context.get("initial_message", "")
        )
        # 2. User transcript with the provided message.
        ChatTranscript.objects.create(
            user=user,
            role="user",
            content=message
        )
        return user
    except Exception as e:
        logger.exception("Error creating new user with ID %s: %s", user.id, e)
        raise


def update_existing_user(user, context: dict, message: str):
    """
    Update an existing user record if necessary and add a new user transcript.
    """
    updated = False
    try:
        # Check if week number changed
        new_week = context.get("week_number")
        if new_week is not None and new_week != user.week_number:
            logger.info("Week number changed for user %s from %s to %s.",
                        user.id, user.week_number, new_week)
            user.week_number = new_week
            updated = True

        # Check if initial message changed
        new_initial_message = context.get("initial_message")
        if new_initial_message and new_initial_message != user.initial_message:
            logger.info(
                "Initial message changed for user %s. Updating transcript.", user.id)
            user.initial_message = new_initial_message
            # Create a new assistant transcript for the updated initial message
            ChatTranscript.objects.create(
                user=user,
                role="assistant",
                content=new_initial_message
            )
            updated = True

        # Always create a transcript for the new user message
        ChatTranscript.objects.create(
            user=user,
            role="user",
            content=message
        )

        if updated:
            user.save()
        return user
    except Exception as e:
        logger.exception("Error updating user %s: %s", user.id, e)
        raise


def ingest_individual_request(participant_id: str, data: dict):
    """
    Ingests an individual request by either creating a new user record or updating
    an existing one. The operation is wrapped in an atomic transaction for consistency.
    """
    logger.info("Processing request for participant ID: %s", participant_id)
    context = data.get("context", {})
    message = data.get("message", "")

    try:
        with transaction.atomic():
            # Provide a default for created_at to avoid null value issues.
            user, created = User.objects.get_or_create(
                id=participant_id,
                defaults={'created_at': timezone.now()}
            )
            if created:
                logger.info(
                    "Participant ID %s not found. Creating a new record.", participant_id)
                create_new_user(user, context, message)
            else:
                logger.info(
                    "Participant ID %s exists. Processing update.", participant_id)
                update_existing_user(user, context, message)
    except Exception as e:
        logger.exception(
            "Error processing request for participant ID %s: %s", participant_id, e)
        raise


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
        GroupChatTranscript.objects.create(
            group=group, role="assistant", content=group.initial_message
        )

        # Create and add participants to the group
        for participant in context.get("participants", []):
            user, user_created = User.objects.get_or_create(
                id=participant["id"])
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

        GroupChatTranscript.objects.create(
            group=group, role="user", content=message, sender=sender
        )
    else:
        logger.info(f"Group ID {group_id} exists.")
        updated = False

        # Check if week_number has changed and update if needed.
        new_week = context.get("week_number")
        if new_week is not None and new_week != group.week_number:
            logger.info(
                f"Week number changed for group {group_id} from {group.week_number} to {new_week}."
            )
            group.week_number = new_week
            updated = True

        # Check if the initial message has changed and update transcript accordingly.
        new_initial_message = context.get("initial_message")
        if new_initial_message and new_initial_message != group.initial_message:
            logger.info(
                f"Initial message changed for group {group_id}. Updating transcript."
            )
            group.initial_message = new_initial_message
            GroupChatTranscript.objects.create(
                group=group, role="assistant", content=new_initial_message
            )
            updated = True

        # Update or add new participants before saving the user message transcript.
        for participant in context.get("participants", []):
            user, user_created = User.objects.get_or_create(
                id=participant["id"])
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
        GroupChatTranscript.objects.create(
            group=group, role="user", content=message, sender=sender
        )

        if updated:
            group.save()


def sanitize_name(name: str) -> str:
    """
    Remove any characters that are not letters, digits, underscores, or hyphens.
    If the sanitized name is empty, return a default value.
    """
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', name)
    return sanitized if sanitized else "default"


def load_individual_chat_history(user_id: str):
    logger.info(f"Loading chat history for participant: {user_id}")

    # Retrieve all transcripts in chronological order
    transcripts = ChatTranscript.objects.filter(
        user_id=user_id).order_by("created_at")

    # Get the most recent user transcript
    latest_user_transcript = (
        ChatTranscript.objects.filter(user_id=user_id, role="user")
        .order_by("-created_at")
        .first()
    )

    # Build chat history, excluding the latest user message
    history = []
    for t in transcripts:
        if latest_user_transcript and t.id == latest_user_transcript.id:
            continue

        if t.role == "user":
            sender_name = t.user.name if t.user.name else "user"
        else:  # role is assistant
            sender_name = t.user.school_mascot if t.user.school_mascot else "assistant"

        sender_name = sanitize_name(sender_name)
        history.append({
            "role": t.role,
            "content": t.content,
            "name": sender_name,
        })

    # Extract only the message content for the latest user message
    latest_user_message_content = latest_user_transcript.content if latest_user_transcript else ""

    return history, latest_user_message_content


def load_detailed_transcript(group_id: str):
    logger.info(f"Loading detailed transcript for group ID: {group_id}")
    transcripts = GroupChatTranscript.objects.filter(
        group_id=group_id).order_by("created_at")
    messages = []
    for t in transcripts:
        sender_name = t.sender.name if t.sender else "assistant"  # TODO: pipe mascot name
        messages.append({
            "sender": sender_name,
            "role": t.role,
            "timestamp": str(t.created_at),
            "content": t.content
        })
    return json.dumps(messages, indent=2)


def load_chat_history_json_group(group_id: str):
    logger.info(f"Loading chat history for group ID: {group_id}")
    transcripts = GroupChatTranscript.objects.filter(
        group_id=group_id).order_by("created_at")
    history = [{"role": t.role, "content": t.content} for t in transcripts]
    return history


def get_latest_assistant_response(user_id: str):
    logger.info(
        f"Fetching latest assistant response for participant with id: {user_id}")

    # Retrieve the most recent assistant response for the given user
    latest_assistant_transcript = (
        ChatTranscript.objects.filter(user_id=user_id, role="assistant")
        .order_by("-created_at")
        .first()
    )

    # Return the content if a transcript exists; otherwise, return None
    return latest_assistant_transcript.content if latest_assistant_transcript else None


def save_assistant_response(user_id: str, response):
    logger.info(f"Saving assistant response for participant: {user_id}")
    user = User.objects.get(id=user_id)
    ChatTranscript.objects.create(
        user=user, role="assistant", content=response)
    logger.info("Assistant Response saved successfully.")


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


INSTRUCTION_PROMPT_TEMPLATE = (
    "Using the below system prompt as your guide, engage with the user in a manner that reflects your assigned persona and follows the activity instructions"
    "System Prompt: {system}\n\n"
    "Assigned Persona: {persona}\n\n"
    "Assistant Name: {assistant_name}\n\n"
    "Activity: {activity}\n\n"
)


def load_instruction_prompt(user_id: str):
    try:
        user = User.objects.get(id=user_id)
        week = user.week_number
        assistant_name = user.school_mascot if user.school_mascot else "Assistant"
    except User.DoesNotExist:
        logger.warning(
            f"User with id {user_id} not found. Using default prompt.")
        week = None
        assistant_name = "Assistant"

    # Load the most recent controls record
    try:
        controls = Control.objects.latest('created_at')
    except Control.DoesNotExist:
        controls = Control.objects.create()

    # Retrieve the prompt for the given week, falling back to a default if none is found
    if week is not None:
        prompt_obj = Prompt.objects.filter(week=week).last()
    else:
        prompt_obj = None

    activity = prompt_obj.activity if prompt_obj else controls.default

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
        controls = Control.objects.latest('created_at')
    except Control.DoesNotExist:
        controls = Control.objects.create()
    if len(controls.moderation) > 0:
        return controls.moderation
    return MODERATION_MESSAGE_DEFAULT
