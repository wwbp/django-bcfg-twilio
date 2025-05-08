from django.utils import timezone
from chat.models import BaseChatTranscript, IndividualChatTranscript, MessageType
from chat.services.individual_crud import load_individual_chat_history


def test_no_transcripts(user_factory):
    user = user_factory()
    history, latest_message = load_individual_chat_history(user)
    assert history == []
    assert latest_message == ""


def test_single_user_transcript(user_factory, individual_session_factory):
    user = user_factory()
    session = individual_session_factory(user=user)
    now = timezone.now()
    latest_transcript = IndividualChatTranscript.objects.create(
        session=session, role=BaseChatTranscript.Role.USER, content="Hello", created_at=now
    )
    history, latest_message = load_individual_chat_history(user)
    assert history == []
    assert latest_message == f"[Sender: {latest_transcript.session.user.name}]: " + "Hello"


def test_multiple_transcripts(user_factory, individual_session_factory):
    user = user_factory()
    session = individual_session_factory(user=user)
    session2 = individual_session_factory(user=user, week_number=2)
    now = timezone.now()
    IndividualChatTranscript.objects.create(
        session=session, role=BaseChatTranscript.Role.USER, content="Hello", created_at=now
    )
    IndividualChatTranscript.objects.create(
        session=session,
        role=BaseChatTranscript.Role.ASSISTANT,
        content="Hi, how can I help?",
        created_at=now + timezone.timedelta(seconds=10),
    )
    latest_transcript = IndividualChatTranscript.objects.create(
        session=session2,
        role=BaseChatTranscript.Role.USER,
        content="I need assistance",
        created_at=now + timezone.timedelta(seconds=20),
    )

    history, latest_message = load_individual_chat_history(user)
    expected_history = [
        {
            "role": BaseChatTranscript.Role.USER,
            "content": f"[Timestamp: {now}| Message Type: {MessageType.INITIAL}]: " + "Hello",
            "name": user.name,
        },
        {
            "role": BaseChatTranscript.Role.ASSISTANT,
            "content": f"[Timestamp: {now + timezone.timedelta(seconds=10)}| Message Type: {MessageType.INITIAL}]: "
            + "Hi, how can I help?",
            "name": user.school_mascot,
        },
    ]
    assert history == expected_history
    assert latest_message == f"[Sender: {latest_transcript.session.user.name}]: " + "I need assistance"


def test_assistant_without_mascot(user_factory, individual_session_factory):
    user_no_mascot = user_factory(school_mascot="")
    session = individual_session_factory(user=user_no_mascot)
    now = timezone.now()
    IndividualChatTranscript.objects.create(
        session=session, role=BaseChatTranscript.Role.ASSISTANT, content="Welcome", created_at=now
    )
    latest_transcript = IndividualChatTranscript.objects.create(
        session=session,
        role=BaseChatTranscript.Role.USER,
        content="Thank you",
        created_at=now + timezone.timedelta(seconds=5),
    )

    history, latest_message = load_individual_chat_history(user_no_mascot)
    expected_history = [
        {
            "role": BaseChatTranscript.Role.ASSISTANT,
            "content": f"[Timestamp: {now}| Message Type: {MessageType.INITIAL}]: " + "Welcome",
            "name": BaseChatTranscript.Role.ASSISTANT,  # Fallback when school_mascot is empty
        },
    ]
    assert history == expected_history
    assert latest_message == f"[Sender: {latest_transcript.session.user.name}]: " + "Thank you"


def test_flagged_moderation_message_ignored(user_factory, individual_session_factory):
    user = user_factory()
    session = individual_session_factory(user=user)
    now = timezone.now()
    IndividualChatTranscript.objects.create(
        session=session,
        role=BaseChatTranscript.Role.ASSISTANT,
        content="Hi, how can I help?",
        created_at=now,
    )
    IndividualChatTranscript.objects.create(
        session=session,
        role=BaseChatTranscript.Role.USER,
        content="I need assistance with killing",
        moderation_status=BaseChatTranscript.ModerationStatus.FLAGGED,
        created_at=now + timezone.timedelta(seconds=10),
    )
    # latest message
    latest_transcript = IndividualChatTranscript.objects.create(
        session=session,
        role=BaseChatTranscript.Role.USER,
        content="Hello",
        created_at=now + timezone.timedelta(seconds=20),
    )

    history, latest_message = load_individual_chat_history(user)
    expected_history = [
        {
            "role": BaseChatTranscript.Role.ASSISTANT,
            "content": f"[Timestamp: {now}| Message Type: {MessageType.INITIAL}]: " + "Hi, how can I help?",
            "name": user.school_mascot,
        },
    ]
    assert history == expected_history
    assert latest_message == f"[Sender: {latest_transcript.session.user.name}]: " + "Hello"
