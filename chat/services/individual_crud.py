from django.utils import timezone
import re
import logging

from chat.serializers import IndividualIncomingMessage

from ..models import (
    BaseChatTranscript,
    GroupChatTranscript,
    GroupSession,
    IndividualSession,
    User,
    IndividualChatTranscript,
    IndividualPrompt,
    ControlConfig,
)
from django.db import transaction

logger = logging.getLogger(__name__)


def ingest_request(participant_id: str, individual_incoming_message: IndividualIncomingMessage):
    """
    Ingests an individual request by either creating a new user record or updating
    an existing one. The operation is wrapped in an atomic transaction for consistency.
    """
    logger.info("Processing request for participant ID: %s", participant_id)

    with transaction.atomic():
        # Provide a default for created_at to avoid null value issues.
        user, _ = User.objects.update_or_create(
            id=participant_id,
            defaults={
                "created_at": timezone.now(),
                "school_name": individual_incoming_message.context.school_name,
                "school_mascot": individual_incoming_message.context.school_mascot,
                "name": individual_incoming_message.context.name,
            },
        )
        session, created_session = IndividualSession.objects.get_or_create(
            user=user,
            week_number=individual_incoming_message.context.week_number,
            message_type=individual_incoming_message.context.message_type,
        )

        if not user.group:
            # we only care about the initial message if the user is not in a group condition, because
            # if the user is in the group condition, we already captured the initial message in the
            # group session's transcript
            if created_session:
                # if we created a new session, we need to add the initial message to it
                IndividualChatTranscript.objects.create(
                    session=session,
                    role=BaseChatTranscript.Role.ASSISTANT,
                    content=individual_incoming_message.context.initial_message,
                )
            else:
                if session.initial_message != individual_incoming_message.context.initial_message and not user.is_test:
                    logger.error(
                        f"Got new initial_message for existing individual session {session}. "
                        f"New message: '{individual_incoming_message.context.initial_message}'."
                        +" Not updating existing initial_message."
                    )

        # in either case, we need to add the user message to the transcript
        user_chat_transcript = IndividualChatTranscript.objects.create(
            session=session, role=BaseChatTranscript.Role.USER, content=individual_incoming_message.message
        )

    return user, session, user_chat_transcript


def _sanitize_name(name: str) -> str:
    """
    Remove any characters that are not letters, digits, underscores, or hyphens.
    If the sanitized name is empty, return a default value.
    """
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "", name)
    return sanitized if sanitized else "default"


def load_individual_and_group_chat_history_for_direct_messaging(user: User):
    logger.info(f"Loading chat history for participant and their group for direct-messaging: {user.id}")
    group_sessions = GroupSession.objects.filter(group=user.group).order_by("created_at")
    assistant_name = user.school_mascot
    history: list[dict] = []
    for gs in group_sessions:
        group_transcripts = (
            GroupChatTranscript.objects.filter(session=gs)
            .exclude(moderation_status=BaseChatTranscript.ModerationStatus.FLAGGED)
            .order_by("created_at")
        )
        for t in group_transcripts:
            if t.role == BaseChatTranscript.Role.USER:
                sender_name = t.sender.name if t.sender else BaseChatTranscript.Role.USER
            else:
                # assistant
                sender_name = assistant_name

            sender_name = _sanitize_name(sender_name)  # type: ignore[arg-type]
            history.append(
                {
                    "role": t.role,
                    "content": t.content,
                    "name": sender_name,
                }
            )
    individual_transcripts = (
        IndividualChatTranscript.objects.filter(session__user_id=user.id)
        .exclude(moderation_status=BaseChatTranscript.ModerationStatus.FLAGGED)
        .order_by("created_at")
    )
    latest_user_transcript = (
        IndividualChatTranscript.objects.filter(session__user_id=user.id, role=BaseChatTranscript.Role.USER)
        .order_by("-created_at")
        .first()
    )
    for t in individual_transcripts:
        if latest_user_transcript and t.id == latest_user_transcript.id:
            continue

        if t.role == BaseChatTranscript.Role.USER:
            sender_name = t.session.user.name if t.session.user.name else BaseChatTranscript.Role.USER
        else:  # role is assistant
            sender_name = (
                t.session.user.school_mascot if t.session.user.school_mascot else BaseChatTranscript.Role.ASSISTANT
            )

        sender_name = _sanitize_name(sender_name)  # type: ignore[arg-type]
        history.append(
            {
                "role": t.role,
                "content": t.content,
                "name": sender_name,
            }
        )

    latest_user_message_content = latest_user_transcript.content if latest_user_transcript else ""

    return history, latest_user_message_content


def load_individual_chat_history(user: User):
    logger.info(f"Loading chat history for participant: {user.id}")

    # Retrieve all transcripts in chronological order
    transcripts = (
        IndividualChatTranscript.objects.filter(session__user_id=user.id)
        .exclude(moderation_status=BaseChatTranscript.ModerationStatus.FLAGGED)
        .order_by("created_at")
    )

    # Get the most recent user transcript
    latest_user_transcript = (
        IndividualChatTranscript.objects.filter(session__user_id=user.id, role=BaseChatTranscript.Role.USER)
        .order_by("-created_at")
        .first()
    )

    # Build chat history, excluding the latest user message
    history = []
    for t in transcripts:
        if latest_user_transcript and t.id == latest_user_transcript.id:
            continue

        if t.role == BaseChatTranscript.Role.USER:
            sender_name = t.session.user.name if t.session.user.name else BaseChatTranscript.Role.USER
        else:  # role is assistant
            sender_name = (
                t.session.user.school_mascot if t.session.user.school_mascot else BaseChatTranscript.Role.ASSISTANT
            )

        sender_name = _sanitize_name(sender_name)  # type: ignore[arg-type]
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


def load_instruction_prompt_for_direct_messaging(user: User):
    logger.info(f"Loading instruction prompt for direct-messaging group participant: {user.id}")
    # get latest session for the user
    session = user.sessions.order_by("-created_at").first()
    week = session.week_number
    message_type = session.message_type
    assistant_name = user.school_mascot if user.school_mascot else "Assistant"

    # Load the most recent controls record
    persona = ControlConfig.retrieve(ControlConfig.ControlConfigKey.GROUP_DIRECT_MESSAGE_PERSONA_PROMPT)  # type: ignore[arg-type]
    system = ControlConfig.retrieve(ControlConfig.ControlConfigKey.SYSTEM_PROMPT)  # type: ignore[arg-type]
    if not persona or not system:
        raise ValueError("System or Persona prompt not found in ControlConfig.")

    try:
        activity = IndividualPrompt.objects.get(week=week, message_type=message_type).activity
    except IndividualPrompt.DoesNotExist as err:
        logger.error(f"Error retrieving activity for week '{week}' and type '{message_type}': {err}")
        raise

    # Format the final prompt using the template
    instruction_prompt = INSTRUCTION_PROMPT_TEMPLATE.format(
        system=system,
        persona=persona,
        assistant_name=assistant_name,
        activity=activity,
    )
    return instruction_prompt


def load_instruction_prompt(user: User):
    # get latest session for the user
    session = user.sessions.order_by("-created_at").first()
    week = session.week_number
    message_type = session.message_type
    assistant_name = user.school_mascot if user.school_mascot else "Assistant"

    # Load the most recent controls record
    persona = ControlConfig.retrieve(ControlConfig.ControlConfigKey.PERSONA_PROMPT)  # type: ignore[arg-type]
    system = ControlConfig.retrieve(ControlConfig.ControlConfigKey.SYSTEM_PROMPT)  # type: ignore[arg-type]
    if not persona or not system:
        raise ValueError("System or Persona prompt not found in ControlConfig.")

    try:
        activity = IndividualPrompt.objects.get(week=week, message_type=message_type).activity
    except IndividualPrompt.DoesNotExist as err:
        logger.error(f"Error retrieving activity for week '{week}' and type '{message_type}': {err}")
        raise

    # Format the final prompt using the template
    instruction_prompt = INSTRUCTION_PROMPT_TEMPLATE.format(
        system=system,
        persona=persona,
        assistant_name=assistant_name,
        activity=activity,
    )
    return instruction_prompt
