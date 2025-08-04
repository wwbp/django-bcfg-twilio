import logging
import re
from django.db.models import Q

from chat.serializers import GroupIncomingMessage, GroupIncomingInitialMessage


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


def _validate_and_truncate_name(name: str, participant_id: str = "") -> str:
    """
    Validate name length and truncate if necessary.

    Args:
        name: The name to validate and potentially truncate
        participant_id: The participant ID for logging purposes

    Returns:
        The validated/truncated name
    """
    if len(name) > 50:
        logger.error(
            f"Name for participant {participant_id} is too long "
            f"(max 50 characters) - truncating to prevent database error"
        )
        # Truncate to 50 characters to prevent database error
        return name[:50]

    return name


def _get_or_create_session(group: Group, week_number: int, message_type: str, initial_message: str | None):
    if message_type == MessageType.CHECK_IN:
        raise ValueError(f"Group session cannot be of type {MessageType.CHECK_IN}.")

    session, created_session = GroupSession.objects.get_or_create(
        group=group,
        week_number=week_number,
        message_type=message_type,
    )
    GroupChatTranscript.persist_initial_message_if_necessary(group, initial_message, session, created_session)

    return session


def _remove_deleted_group_participants(
    group: Group, group_incoming_message: GroupIncomingMessage | GroupIncomingInitialMessage
):
    existing_group_users: list[User] = list(group.users.all())  # type: ignore[attrib]
    inbound_participants = group_incoming_message.context.participants
    for user in existing_group_users:
        matching_inbound_participant = next((ip for ip in inbound_participants if ip.id == user.id), None)
        if not matching_inbound_participant:
            # this is a valid use case if a participant leaves the study
            logger.info(f"Removing user {user.id} from group {group.id}.")
            group.users.remove(user)  # type: ignore[attrib]


def _validate_create_and_update_group_participants(
    group: Group,
    group_incoming_message: GroupIncomingMessage | GroupIncomingInitialMessage,
    sender_id: str | None,
    group_just_created: bool,
):
    inbound_participants_payload = group_incoming_message.context.participants
    found_sender = False if sender_id else True  # if sender_id is None, the message is an initial message from the bot

    for participant in inbound_participants_payload:
        if participant.id == sender_id:
            found_sender = True

        # if user exists, update attributes. Group membership shouldn't change but we handle just in case
        existing_users = list(User.objects.filter(id=participant.id).all())
        if existing_users:
            existing_user = existing_users[0]
            changed = False
            if existing_user.group != group:
                logger.warning(
                    f"{group.id}: User {existing_user.id} is already in group "
                    f"{existing_user.group.id if existing_user.group else None}. "
                    f"Changing group association to {group.id}."
                )
                existing_user.group = group
                changed = True

            # Validate and truncate user data
            validated_name = _validate_and_truncate_name(participant.name, participant.id)

            if (
                existing_user.school_name != group_incoming_message.context.school_name
                or existing_user.school_mascot != group_incoming_message.context.school_mascot
                or existing_user.name != validated_name
            ):
                existing_user.school_name = group_incoming_message.context.school_name
                existing_user.school_mascot = group_incoming_message.context.school_mascot
                existing_user.name = validated_name
                changed = True
            if changed:
                existing_user.save()

        # if user does not exist, we create it
        else:
            if not group_just_created:
                # we should not need to add new users to existing groups. We will do it, but we report it
                logger.error(f"Existing group does not yet have user {participant.id}. Creating new user.")

            # Validate and truncate user data
            validated_name = _validate_and_truncate_name(participant.name, participant.id)

            User.objects.create(
                id=participant.id,
                name=validated_name,
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


def ingest_initial_message(group_id: str, group_incoming_message: GroupIncomingInitialMessage):
    with transaction.atomic():
        group, group_created = Group.objects.get_or_create(
            id=group_id,
        )
        _remove_deleted_group_participants(group, group_incoming_message)
        _validate_create_and_update_group_participants(
            group, group_incoming_message, sender_id=None, group_just_created=group_created
        )
        session = _get_or_create_session(
            group,
            week_number=group_incoming_message.context.week_number,
            message_type=group_incoming_message.context.message_type,
            initial_message=None,
        )
        assistant_chat_transcript = GroupChatTranscript.objects.create(
            session=session,
            role=BaseChatTranscript.Role.ASSISTANT,
            content=group_incoming_message.message,
            hub_initiated=True,
            assistant_strategy_phase=GroupStrategyPhase.AUDIENCE,
        )

    return group, assistant_chat_transcript


def load_instruction_prompt(session: GroupSession, strategy_phase: GroupStrategyPhase) -> str:
    week = session.week_number
    user = User.objects.filter(group=session.group).first()
    assistant_name = user.school_mascot if user else BaseChatTranscript.Role.ASSISTANT
    school_name = user.school_name if user else ""

    # We use a different persona prompt for the strategy phase
    if strategy_phase == GroupStrategyPhase.SUMMARY:
        persona_key = ControlConfig.ControlConfigKey.GROUP_SUMMARY_PERSONA_PROMPT
    else:
        persona_key = ControlConfig.ControlConfigKey.PERSONA_PROMPT
    persona = ControlConfig.retrieve(persona_key)
    system = ControlConfig.retrieve(ControlConfig.ControlConfigKey.SYSTEM_PROMPT)
    if not persona or not system:
        raise ValueError("System or Persona prompt not found in ControlConfig.")

    if strategy_phase == GroupStrategyPhase.AUDIENCE:
        activity = ControlConfig.retrieve(ControlConfig.ControlConfigKey.GROUP_AUDIENCE_STRATEGY_PROMPT)
        if not activity:
            raise ValueError("GROUP_AUDIENCE_STRATEGY_PROMPT not found in ControlConfig.")
    elif strategy_phase == GroupStrategyPhase.REMINDER:
        activity = ControlConfig.retrieve(ControlConfig.ControlConfigKey.GROUP_REMINDER_STRATEGY_PROMPT)
        if not activity:
            raise ValueError("GROUP_REMINDER_STRATEGY_PROMPT not found in ControlConfig.")
    else:
        # Treat initial and reminder as the same for the purpose of loading the prompt
        message_type = MessageType.INITIAL if session.message_type == MessageType.REMINDER else session.message_type
        try:
            activity = GroupPrompt.objects.get(
                week=week, message_type=message_type, strategy_type=strategy_phase
            ).activity
        except GroupPrompt.DoesNotExist as err:
            logger.error(
                f"Prompt not found for week {week}, message_type {message_type} and type {strategy_phase}: {err}"
            )
            raise err

    # Pull the template out of ControlConfig (fallback to the constant if missing)
    template = ControlConfig.retrieve(ControlConfig.ControlConfigKey.GROUP_INSTRUCTION_PROMPT_TEMPLATE)  # type: ignore[arg-type]
    if not template:
        raise ValueError("group-prompt template not found in ControlConfig.")

    # Format the final prompt using the template
    instruction_prompt = template.format(
        system=system,
        persona=persona,
        assistant_name=assistant_name,
        school_name=school_name,
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
    if session.message_type == MessageType.REMINDER:
        # if we are in a reminder session, we also need to load messages
        # from the associated initial session, because the reminder is about the initial message
        # and the chatbot should know about the full conversation
        transcripts = GroupChatTranscript.objects.filter(
            Q(
                session__group=session.group,
                session__week_number=session.week_number,
                session__message_type=MessageType.INITIAL,
            )
            | Q(session=session)
        ).order_by("created_at")
    else:
        transcripts = GroupChatTranscript.objects.filter(session=session).order_by("created_at")
    latest_user_transcript = transcripts.filter(role=BaseChatTranscript.Role.USER).last()
    assistant_name = (
        latest_user_transcript.sender.school_mascot
        if latest_user_transcript and latest_user_transcript.sender
        else BaseChatTranscript.Role.ASSISTANT
    )
    history: list[dict] = []
    for t in transcripts:
        if (
            latest_user_transcript and t.id == latest_user_transcript.id  # type: ignore[attrib]
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
                "content": f"[Timestamp: {t.created_at}| Strategy Type: {t.assistant_strategy_phase}]: " + t.content,
                "name": sender_name,
            }
        )
    latest_sender_message = (
        f"[Sender/User Name: {latest_user_transcript.sender.name}]: " + latest_user_transcript.content
        if latest_user_transcript and latest_user_transcript.sender
        else ""
    )
    return history, latest_sender_message
