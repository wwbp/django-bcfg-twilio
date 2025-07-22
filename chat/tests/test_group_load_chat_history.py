from django.utils import timezone
from chat.models import BaseChatTranscript, GroupStrategyPhase, MessageType
from chat.services.group_crud import load_group_chat_history


def test_no_transcripts(group_factory, group_session_factory):
    group = group_factory()
    session = group_session_factory(group=group, week_number=1, message_type=MessageType.INITIAL)
    history, latest = load_group_chat_history(session)
    assert history == []
    assert latest == ""


def test_only_initial_message_and_user_message_excluded(
    group_factory, user_factory, group_session_factory, group_chat_transcript_factory
):
    group = group_factory()
    # create two users in group
    u1 = user_factory(id="u1", name="Max", group=group, school_mascot="Eagle")
    u2 = user_factory(id="u2", name="Bob", group=group, school_mascot="Eagle")

    # create new and old sessions with chat transcripts
    old_session = group_session_factory(group=group, week_number=9, message_type=MessageType.INITIAL)
    current_session = group_session_factory(group=group, week_number=10, message_type=MessageType.INITIAL)
    now = timezone.now()
    group_chat_transcript_factory(
        session=old_session,
        role=BaseChatTranscript.Role.ASSISTANT,
        content="Some older message",
        created_at=now - timezone.timedelta(days=1),
        assistant_strategy_phase=GroupStrategyPhase.AUDIENCE,
        hub_initiated=True,
    )
    group_chat_transcript_factory(
        session=current_session,
        role=BaseChatTranscript.Role.ASSISTANT,
        content="Hello",
        created_at=now,
        assistant_strategy_phase=GroupStrategyPhase.AUDIENCE,
    )
    latest_transcript = group_chat_transcript_factory(
        session=current_session,
        role=BaseChatTranscript.Role.USER,
        content="Hi group",
        sender=u1,
        created_at=now + timezone.timedelta(seconds=10),
    )

    # load history should exclude that last user message from history and return it as `latest_sender_message`
    history, latest = load_group_chat_history(current_session)

    # Only the initial assistant message should be in history
    assert history == [
        {
            "role": BaseChatTranscript.Role.ASSISTANT,
            "content": f"[Timestamp: {now}| Strategy Type: {GroupStrategyPhase.AUDIENCE}]: " + "Hello",
            "name": "Eagle",
        }
    ]
    assert latest == f"[Sender/User Name: {latest_transcript.sender.name}]: " + "Hi group"


def test_only_reminder_session_includes_initial(
    group_factory, user_factory, group_session_factory, group_chat_transcript_factory
):
    group = group_factory()
    # create two users in group
    u1 = user_factory(id="u1", name="Max", group=group, school_mascot="Eagle")
    u2 = user_factory(id="u2", name="Bob", group=group, school_mascot="Eagle")

    # create new and old sessions with chat transcripts
    old_week_session = group_session_factory(group=group, week_number=9, message_type=MessageType.INITIAL)
    current_week_initial_session = group_session_factory(group=group, week_number=10, message_type=MessageType.INITIAL)
    current_week_reminder_session = group_session_factory(
        group=group, week_number=10, message_type=MessageType.REMINDER
    )
    now = timezone.now()
    group_chat_transcript_factory(
        session=old_week_session,
        role=BaseChatTranscript.Role.ASSISTANT,
        content="Some older message",
        created_at=now - timezone.timedelta(days=1),
        assistant_strategy_phase=GroupStrategyPhase.AUDIENCE,
        hub_initiated=True,
    )
    group_chat_transcript_factory(
        session=current_week_initial_session,
        role=BaseChatTranscript.Role.ASSISTANT,
        content="Hello",
        created_at=now - timezone.timedelta(hours=3),
        assistant_strategy_phase=GroupStrategyPhase.AUDIENCE,
    )
    group_chat_transcript_factory(
        session=current_week_initial_session,
        role=BaseChatTranscript.Role.USER,
        content="Hi group",
        sender=u1,
        created_at=now - timezone.timedelta(hours=2),
    )
    group_chat_transcript_factory(
        session=current_week_reminder_session,
        role=BaseChatTranscript.Role.ASSISTANT,
        content="Hello again - reminding you",
        created_at=now - timezone.timedelta(hours=1),
        assistant_strategy_phase=GroupStrategyPhase.AUDIENCE,
    )
    latest_transcript = group_chat_transcript_factory(
        session=current_week_reminder_session,
        role=BaseChatTranscript.Role.USER,
        content="Hi group after reminder",
        sender=u1,
        created_at=now,
    )

    # load history should exclude that last user message from history and return it as `latest_sender_message`
    history, latest = load_group_chat_history(current_week_reminder_session)

    # Only the initial assistant message should be in history
    assert history == [
        {
            "role": BaseChatTranscript.Role.ASSISTANT,
            "content": f"[Timestamp: {now - timezone.timedelta(hours=3)}| "
            f"Strategy Type: {GroupStrategyPhase.AUDIENCE}]: " + "Hello",
            "name": "Eagle",
        },
        {
            "role": BaseChatTranscript.Role.USER,
            "content": f"[Timestamp: {now - timezone.timedelta(hours=2)}| Strategy Type: None]: " + "Hi group",
            "name": u1.name,
        },
        {
            "role": BaseChatTranscript.Role.ASSISTANT,
            "content": f"[Timestamp: {now - timezone.timedelta(hours=1)}| "
            f"Strategy Type: {GroupStrategyPhase.AUDIENCE}]: " + "Hello again - reminding you",
            "name": "Eagle",
        },
    ]
    assert latest == f"[Sender/User Name: {latest_transcript.sender.name}]: " + "Hi group after reminder"


def test_history_with_moderation_flagged(
    group_factory, user_factory, group_session_factory, group_chat_transcript_factory
):
    group = group_factory()
    u1 = user_factory(id="u1", name="Al!ce-1", school_mascot="Eagle", group=group)
    u2 = user_factory(id="u2", name="B@b$", school_mascot="Eagle", group=group)

    session = group_session_factory(group=group, week_number=2, message_type=MessageType.INITIAL)

    group_chat_transcript_factory(
        session=session, role=BaseChatTranscript.Role.ASSISTANT, content="Initial assistant message", hub_initiated=True
    )
    group_chat_transcript_factory(session=session, role=BaseChatTranscript.Role.USER, content="First", sender=u1)
    group_chat_transcript_factory(
        session=session,
        role=BaseChatTranscript.Role.USER,
        content="Bad content",
        sender=u2,
        moderation_status=BaseChatTranscript.ModerationStatus.FLAGGED,
    )
    group_chat_transcript_factory(session=session, role=BaseChatTranscript.Role.ASSISTANT, content="Reply1")
    latest_transcript = group_chat_transcript_factory(
        session=session, role=BaseChatTranscript.Role.USER, content="Final", sender=u2
    )

    history, latest = load_group_chat_history(session)

    expected_roles = [
        BaseChatTranscript.Role.ASSISTANT,  # initial
        BaseChatTranscript.Role.USER,  # First u1
        BaseChatTranscript.Role.ASSISTANT,  # Reply1
    ]
    assert [h["role"] for h in history] == expected_roles

    assert history[1]["name"] == "Alce-1"
    assert history[2]["name"] == "Eagle"
    assert latest == f"[Sender/User Name: {latest_transcript.sender.name}]: " + "Final"
