import logging
import re

from chat.serializers import GroupIncomingMessage


from ..models import (
    BaseChatTranscript,
    ControlConfig,
    Group,
    GroupChatTranscript,
    GroupSession,
    GroupStrategyPhase,
    MessageType,
    GroupPrompt,
    User,
)
from django.db import transaction

logger = logging.getLogger(__name__)


def _get_or_create_session(group: Group, week_number: int, message_type: str, initial_message: str):
    if message_type == MessageType.CHECK_IN:
        raise ValueError(f"Group session cannot be of type {MessageType.CHECK_IN}.")

    session, created_session = GroupSession.objects.get_or_create(
        group=group,
        week_number=week_number,
        message_type=message_type,
    )

    if created_session:
        # if we created a new session, we need to add the initial message to it
        GroupChatTranscript.objects.create(
            session=session,
            role=BaseChatTranscript.Role.ASSISTANT,
            content=initial_message,
            assistant_strategy_phase=GroupStrategyPhase.AUDIENCE,
        )
    else:
        if session.initial_message != initial_message and not group.is_test:
            logger.error(
                f"Got new initial_message for existing group session {session}. "
                f"New message: '{initial_message}'. Not updating existing initial_message."
            )

    return session


def _remove_deleted_group_participants(group: Group, group_incoming_message: GroupIncomingMessage):
    existing_group_users: list[User] = list(group.users.all())
    inbound_participants = group_incoming_message.context.participants
    for user in existing_group_users:
        matching_inbound_participant = next((ip for ip in inbound_participants if ip.id == user.id), None)
        if not matching_inbound_participant:
            # this is a valid use case if a participant leaves the study
            logger.info(f"Removing user {user.id} from group {group.id}.")
            group.users.remove(user)


def _validate_create_and_update_group_participants(
    group: Group, group_incoming_message: GroupIncomingMessage, sender_id: str, group_just_created: bool
):
    inbound_participants_payload = group_incoming_message.context.participants
    found_sender = False

    for participant in inbound_participants_payload:
        if participant.id == sender_id:
            found_sender = True

        # if user exists, update attributes. Group membership shouldn't change but we handle just in case
        existing_users = list(User.objects.filter(id=participant.id).all())
        if existing_users:
            existing_user = existing_users[0]
            changed = False
            if existing_user.group != group:
                logger.error(
                    f"{group.id}: User {existing_user.id} is already in group {existing_user.group.id}. "
                    f"Changing group association to {group.id}."
                )
                existing_user.group = group
                changed = True
            if (
                existing_user.school_name != group_incoming_message.context.school_name
                or existing_user.school_mascot != group_incoming_message.context.school_mascot
                or existing_user.name != participant.name
            ):
                existing_user.school_name = group_incoming_message.context.school_name
                existing_user.school_mascot = group_incoming_message.context.school_mascot
                existing_user.name = participant.name
                changed = True
            if changed:
                existing_user.save()

        # if user does not exist, we create it
        else:
            if not group_just_created:
                # we should not need to add new users to existing groups. We will do it, but we report it
                logger.error(f"Existing group does not yet have user {participant.id}. Creating new user.")
            User.objects.create(
                id=participant.id,
                name=participant.name,
                school_name=group_incoming_message.context.school_name,
                school_mascot=group_incoming_message.context.school_mascot,
                group=group,
            )

    # lastly, validate that the sender is in the list of participants
    # if not, this is a fatal error
    if not found_sender:
        raise ValueError(f"Sender ID {sender_id} not found in the list of participants: {inbound_participants_payload}")


def ingest_request(group_id: str, group_incoming_message: GroupIncomingMessage):
    """
    Ingests a group request by either creating a new user record or updating
    an existing one. The operation is wrapped in an atomic transaction for consistency.
    """
    logger.info("Processing request for group ID: %s", group_id)

    with transaction.atomic():
        group, group_created = Group.objects.get_or_create(
            id=group_id,
        )
        _remove_deleted_group_participants(group, group_incoming_message)
        _validate_create_and_update_group_participants(
            group, group_incoming_message, group_incoming_message.sender_id, group_just_created=group_created
        )
        sender = User.objects.get(id=group_incoming_message.sender_id)
        session = _get_or_create_session(
            group,
            week_number=group_incoming_message.context.week_number,
            message_type=group_incoming_message.context.message_type,
            initial_message=group_incoming_message.context.initial_message,
        )
        user_chat_transcript = GroupChatTranscript.objects.create(
            session=session, role=BaseChatTranscript.Role.USER, content=group_incoming_message.message, sender=sender
        )

    return group, user_chat_transcript


GROUP_INSTRUCTION_PROMPT_TEMPLATE = (
    "Using the below system prompt as your guide, engage with the group as a participant in a "
    "manner that reflects your assigned persona and follows the conversation stategy instructions"
    "System Prompt: {system}\n\n"
    "Assigned Persona: {persona}\n\n"
    "Assistant Name: {assistant_name}\n\n"
    "Strategy: {strategy}\n\n"
)


def load_instruction_prompt(session: GroupSession, strategy_phase: GroupStrategyPhase) -> str:
    week = session.week_number
    user = User.objects.filter(group=session.group).first()
    assistant_name = user.school_mascot if user else BaseChatTranscript.Role.ASSISTANT

    # Load the most recent controls record
    persona = ControlConfig.retrieve(ControlConfig.ControlConfigKey.PERSONA_PROMPT)  # type: ignore[arg-type]
    system = ControlConfig.retrieve(ControlConfig.ControlConfigKey.SYSTEM_PROMPT)  # type: ignore[arg-type]
    if not persona or not system:
        raise ValueError("System or Persona prompt not found in ControlConfig.")

    try:
        activity = GroupPrompt.objects.get(week=week, strategy_type=strategy_phase).activity
    except GroupPrompt.DoesNotExist as err:
        logger.error(f"Prompt not found for week {week} and type {strategy_phase}: {err}")
        raise

    # Format the final prompt using the template
    instruction_prompt = GROUP_INSTRUCTION_PROMPT_TEMPLATE.format(
        system=system,
        persona=persona,
        assistant_name=assistant_name,
        strategy=activity,
    )
    return instruction_prompt


def _sanitize_name(name: str) -> str:
    """
    Remove any characters that are not letters, digits, underscores, or hyphens.
    If the sanitized name is empty, return a default value.
    """
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "", name)
    return sanitized if sanitized else "default"


def load_group_chat_history(session: GroupSession) -> tuple[list[dict], str]:
    """
    Loads the chat history for a group session.
    """
    transcripts = GroupChatTranscript.objects.filter(session=session).order_by("created_at")
    latest_user_transcript = transcripts.filter(role=BaseChatTranscript.Role.USER).last()
    assistant_name = (
        latest_user_transcript.sender.school_mascot if latest_user_transcript else BaseChatTranscript.Role.ASSISTANT
    )
    history: list[dict] = []
    for t in transcripts:
        if (
            latest_user_transcript and t.id == latest_user_transcript.id
        ) or t.moderation_status == BaseChatTranscript.ModerationStatus.FLAGGED:
            continue

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
                "sender_name": sender_name,
            }
        )
    latest_sender_message = latest_user_transcript.content if latest_user_transcript else ""
    return history, latest_sender_message
