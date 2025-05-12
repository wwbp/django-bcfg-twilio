import pytest
from django.utils import timezone
from datetime import timedelta

from chat.models import BaseChatTranscript, IndividualChatTranscript, GroupStrategyPhase, MessageType
from chat.services.individual_crud import load_individual_and_group_chat_history_for_direct_messaging


@pytest.mark.django_db
def test_no_history(user_factory):
    user = user_factory()
    history, latest_message = load_individual_and_group_chat_history_for_direct_messaging(user)
    assert history == []
    assert latest_message == ""


@pytest.mark.django_db
def test_group_history_only(user_factory, group_chat_transcript_factory):
    user = user_factory()
    now = timezone.now()
    # create a flagged group transcript (should be ignored)
    flagged = group_chat_transcript_factory(
        moderation_status=BaseChatTranscript.ModerationStatus.FLAGGED,
        role=BaseChatTranscript.Role.USER,
        content="Flagged message",
        sender=user,
        created_at=now,
    )
    session = flagged.session

    # create a valid group transcript
    valid = group_chat_transcript_factory(
        session=session,
        moderation_status=BaseChatTranscript.ModerationStatus.NOT_FLAGGED,
        role=BaseChatTranscript.Role.USER,
        content="Valid group message",
        sender=user,
        created_at=now + timedelta(seconds=1),
    )

    # assign the user to the group so the function picks up the session
    user.group = session.group
    user.save()

    history, latest_message = load_individual_and_group_chat_history_for_direct_messaging(user)
    assert latest_message == ""
    expected = [
        {
            "role": BaseChatTranscript.Role.USER,
            "content": f"[Timestamp: {now + timedelta(seconds=1)}| Strategy Type: {None}]: " + "Valid group message",
            "name": user.name,
        },
    ]
    assert history == expected


@pytest.mark.django_db
def test_individual_history_only(user_factory, individual_session_factory):
    user = user_factory()
    session1 = individual_session_factory(user=user)
    session2 = individual_session_factory(user=user, week_number=2)
    now = timezone.now()

    # older user message
    IndividualChatTranscript.objects.create(
        session=session1,
        role=BaseChatTranscript.Role.USER,
        content="First",
        created_at=now,
    )
    # assistant message
    IndividualChatTranscript.objects.create(
        session=session1,
        role=BaseChatTranscript.Role.ASSISTANT,
        content="Assist",
        created_at=now + timedelta(seconds=10),
    )
    # flagged user message (should be ignored)
    IndividualChatTranscript.objects.create(
        session=session2,
        role=BaseChatTranscript.Role.USER,
        content="Flagged",
        moderation_status=BaseChatTranscript.ModerationStatus.FLAGGED,
        created_at=now + timedelta(seconds=20),
    )
    # latest user message (should be returned as latest only)
    latest_transcript = IndividualChatTranscript.objects.create(
        session=session2,
        role=BaseChatTranscript.Role.USER,
        content="Latest",
        created_at=now + timedelta(seconds=30),
    )

    history, latest_message = load_individual_and_group_chat_history_for_direct_messaging(user)
    assert latest_message == f"[Sender/User Name: {latest_transcript.session.user.name}]: " + "Latest"
    expected = [
        {
            "role": BaseChatTranscript.Role.USER,
            "content": f"[Timestamp: {now}| Message Type: {MessageType.INITIAL}]: " + "First",
            "name": user.name,
        },
        {
            "role": BaseChatTranscript.Role.ASSISTANT,
            "content": f"[Timestamp: {now + timedelta(seconds=10)}| Message Type: {MessageType.INITIAL}]: " + "Assist",
            "name": user.school_mascot,
        },
    ]
    assert history == expected


@pytest.mark.django_db
def test_sanitization_combined(user_factory, individual_session_factory, group_chat_transcript_factory):
    # user with special characters in name and mascot
    user = user_factory(name="John Doe!?", school_mascot="Wolf-Pack!")
    session1 = individual_session_factory(user=user)
    now = timezone.now()

    # flagged group transcript (ignored)
    flagged_group = group_chat_transcript_factory(
        moderation_status=BaseChatTranscript.ModerationStatus.FLAGGED,
        role=BaseChatTranscript.Role.USER,
        content="Bad group",
        sender=user,
        created_at=now,
    )
    session = flagged_group.session

    # valid group user transcript
    group_chat_transcript_factory(
        session=session,
        moderation_status=BaseChatTranscript.ModerationStatus.NOT_FLAGGED,
        role=BaseChatTranscript.Role.USER,
        content="Group says hi",
        sender=user,
        created_at=now + timedelta(seconds=1),
    )
    # valid group assistant transcript
    group_chat_transcript_factory(
        session=session,
        moderation_status=BaseChatTranscript.ModerationStatus.NOT_FLAGGED,
        role=BaseChatTranscript.Role.ASSISTANT,
        assistant_strategy_phase=GroupStrategyPhase.AUDIENCE,
        content="Group welcome",
        created_at=now + timedelta(seconds=2),
    )

    # ensure the user is in the group
    user.group = session.group
    user.save()

    # individual assistant transcript (should be included)
    IndividualChatTranscript.objects.create(
        session=session1,
        role=BaseChatTranscript.Role.ASSISTANT,
        content="Assist reply",
        created_at=now + timedelta(seconds=3),
    )
    # individual latest user transcript (should be returned as latest only)
    latest_transcript = IndividualChatTranscript.objects.create(
        session=session1,
        role=BaseChatTranscript.Role.USER,
        content="User latest",
        created_at=now + timedelta(seconds=4),
    )

    history, latest_message = load_individual_and_group_chat_history_for_direct_messaging(user)
    assert latest_message == f"[Sender/User Name: {latest_transcript.session.user.name}]: " + "User latest"
    expected = [
        {
            "role": BaseChatTranscript.Role.USER,
            "content": f"[Timestamp: {now + timedelta(seconds=1)}| Strategy Type: {None}]: " + "Group says hi",
            "name": "JohnDoe",
        },
        {
            "role": BaseChatTranscript.Role.ASSISTANT,
            "content": f"[Timestamp: {now + timedelta(seconds=2)}| Strategy Type: {GroupStrategyPhase.AUDIENCE}]: "
            + "Group welcome",
            "name": "Wolf-Pack",
        },
        {
            "role": BaseChatTranscript.Role.ASSISTANT,
            "content": f"[Timestamp: {now + timedelta(seconds=3)}| Message Type: {MessageType.INITIAL}]: "
            + "Assist reply",
            "name": "Wolf-Pack",
        },
    ]
    assert history == expected
