from django.utils import timezone
import re
import logging

from ..models import (
    BaseChatTranscript,
    IndividualSession,
    User,
    IndividualChatTranscript,
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
            IndividualChatTranscript.objects.create(
                session=session, role=BaseChatTranscript.Role.ASSISTANT, content=context.get("initial_message")
            )
        else:
            if session.initial_message != context.get("initial_message") and not user.is_test:
                logger.error(
                    f"Got new initial_message for existing individual session {session}. "
                    f"New message: '{context.get('initial_message')}'. Not updating existing initial_message."
                )

        # in either case, we need to add the user message to the transcript
        user_chat_transcript = IndividualChatTranscript.objects.create(
            session=session, role=BaseChatTranscript.Role.USER, content=message
        )

    return user, session, user_chat_transcript


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
    transcripts = IndividualChatTranscript.objects.filter(session__user_id=user.id).order_by("created_at")

    # Get the most recent user transcript
    latest_user_transcript = (
        IndividualChatTranscript.objects.filter(session__user_id=user.id, role=BaseChatTranscript.Role.USER)
        .order_by("-created_at")
        .first()
    )

    # Build chat history, excluding the latest user message
    history = []
    for t in transcripts:
        if (
            latest_user_transcript and t.id == latest_user_transcript.id
        ) or t.moderation_status == BaseChatTranscript.ModerationStatus.FLAGGED:
            continue

        if t.role == BaseChatTranscript.Role.USER:
            sender_name = t.session.user.name if t.session.user.name else BaseChatTranscript.Role.USER
        else:  # role is assistant
            sender_name = (
                t.session.user.school_mascot if t.session.user.school_mascot else BaseChatTranscript.Role.ASSISTANT
            )

        sender_name = sanitize_name(sender_name)  # type: ignore[arg-type]
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


# TODO - do we still need these commented out functions?

# def load_detailed_transcript(group_id: str):
#     logger.info(f"Loading detailed transcript for group ID: {group_id}")
#     transcripts = GroupChatTranscript.objects.filter(group_id=group_id).order_by("created_at")
#     messages = []
#     for t in transcripts:
#         sender_name = t.sender.name if t.sender else BaseChatTranscript.Role.ASSISTANT  # TODO: pipe mascot name
#         messages.append({"sender": sender_name, "role": t.role, "timestamp": str(t.created_at), "content": t.content})
#     return json.dumps(messages, indent=2)


# def load_chat_history_json_group(group_id: str):
#     logger.info(f"Loading chat history for group ID: {group_id}")
#     transcripts = GroupChatTranscript.objects.filter(group_id=group_id).order_by("created_at")
#     history = [{"role": t.role, "content": t.content} for t in transcripts]
#     return history


# def get_latest_assistant_response(user_id: str):
#     logger.info(f"Fetching latest assistant response for participant with id: {user_id}")

#     # Retrieve the most recent assistant response for the given user
#     latest_assistant_transcript = (
#         IndividualChatTranscript.objects.filter(session__user_id=user_id, role=BaseChatTranscript.Role.ASSISTANT)
#         .order_by("-created_at")
#         .first()
#     )

#     # Return the content if a transcript exists; otherwise, return None
#     return latest_assistant_transcript.content if latest_assistant_transcript else None


def save_assistant_response(user: User, response: str, session: IndividualSession):
    logger.info(f"Saving assistant response for participant: {user.id}")
    IndividualChatTranscript.objects.create(session=session, role=BaseChatTranscript.Role.ASSISTANT, content=response)
    logger.info("Assistant Response saved successfully.")


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
