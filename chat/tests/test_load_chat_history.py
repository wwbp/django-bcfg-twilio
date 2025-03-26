from django.utils import timezone
from chat.models import ChatTranscript
from chat.crud import load_individual_chat_history


def test_no_transcripts(user_factory):
    user = user_factory()
    history, latest_message = load_individual_chat_history(user.id)
    assert history == []
    assert latest_message == ""


def test_single_user_transcript(user_factory):
    user = user_factory()
    now = timezone.now()
    ChatTranscript.objects.create(user=user, role="user", content="Hello", created_at=now)
    history, latest_message = load_individual_chat_history(user.id)
    assert history == []
    assert latest_message == "Hello"


def test_multiple_transcripts(user_factory):
    user = user_factory()
    now = timezone.now()
    ChatTranscript.objects.create(user=user, role="user", content="Hello", created_at=now)
    ChatTranscript.objects.create(
        user=user,
        role="assistant",
        content="Hi, how can I help?",
        created_at=now + timezone.timedelta(seconds=10),
    )
    ChatTranscript.objects.create(
        user=user, role="user", content="I need assistance", created_at=now + timezone.timedelta(seconds=20)
    )

    history, latest_message = load_individual_chat_history(user.id)
    expected_history = [
        {
            "role": "user",
            "content": "Hello",
            "name": user.name,
        },
        {
            "role": "assistant",
            "content": "Hi, how can I help?",
            "name": user.school_mascot,
        },
    ]
    assert history == expected_history
    assert latest_message == "I need assistance"


def test_assistant_without_mascot(user_factory):
    user_no_mascot = user_factory(school_mascot="")
    now = timezone.now()
    ChatTranscript.objects.create(user=user_no_mascot, role="assistant", content="Welcome", created_at=now)
    ChatTranscript.objects.create(
        user=user_no_mascot, role="user", content="Thank you", created_at=now + timezone.timedelta(seconds=5)
    )

    history, latest_message = load_individual_chat_history(user_no_mascot.id)
    expected_history = [
        {
            "role": "assistant",
            "content": "Welcome",
            "name": "assistant",  # Fallback when school_mascot is empty
        },
    ]
    assert history == expected_history
    assert latest_message == "Thank you"
