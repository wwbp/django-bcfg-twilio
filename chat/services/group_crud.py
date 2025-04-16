import logging

from chat.serializers import GroupIncomingMessage

from ..models import (
    BaseChatTranscript,
    Group,
    GroupChatTranscript,
    GroupSession,
    GroupStrategyPhase,
    MessageType,
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
            assistant_strategy_phase=GroupStrategyPhase.BEFORE_AUDIENCE,
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
