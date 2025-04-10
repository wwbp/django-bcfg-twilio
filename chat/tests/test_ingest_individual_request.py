import pytest
from chat.models import IndividualSession, MessageType, TranscriptRole, User, ChatTranscript
from chat.services.crud import ingest_request


@pytest.fixture
def base_context():
    return {
        "school_name": "Test High",
        "school_mascot": "Tigers",
        "name": "Alice",
        "initial_message": "Hello, world!",
        "week_number": 1,
        "message_type": MessageType.INITIAL,
    }


def test_new_user_creation(base_context):
    """
    When a user is not found, a new record should be created using context data,
    and two ChatTranscript records should be generated.
    """
    participant_id = "new_user_1"
    input_data = {
        "context": base_context,
        "message": "I would like to enroll.",
    }

    ingest_request(participant_id, input_data)

    # Assert that the user was created with correct attributes
    user = User.objects.get(id=participant_id)
    session = user.sessions.order_by("-created_at").first()
    assert user.school_name == "Test High"
    assert user.school_mascot == "Tigers"
    assert user.name == "Alice"
    assert session.initial_message == "Hello, world!"
    assert session.week_number == 1
    assert session.message_type == MessageType.INITIAL

    # Assert that two transcripts were created
    transcripts = ChatTranscript.objects.filter(session=session).order_by("id")
    assert transcripts.count() == 2
    assert transcripts[0].role == TranscriptRole.ASSISTANT
    assert transcripts[0].content == "Hello, world!"
    assert transcripts[1].role == TranscriptRole.USER
    assert transcripts[1].content == "I would like to enroll."


@pytest.fixture
def existing_user():
    user = User.objects.create(
        id="existing_week_update",
        school_name="Old School",
        school_mascot="Lions",
        name="Bob",
    )
    session = IndividualSession.objects.create(
        user=user,
        initial_message="Initial Hello",
        week_number=1,
        message_type=MessageType.SUMMARY,
    )

    return user, session


@pytest.fixture
def existing_transcript(existing_user):
    user, _ = existing_user
    return ChatTranscript.objects.create(
        session=user.current_session, role=TranscriptRole.ASSISTANT, content="Initial Hello"
    )


def test_existing_user_update_session_context(existing_user, existing_transcript):
    """
    When an existing user sends data with a changed week_number,
    the user record should update and a new transcript entry should be added.
    """
    user, session = existing_user
    input_data = {
        "context": {
            "week_number": 2,
            "message_type": MessageType.INITIAL,
            "initial_message": "Initial Hello From Week 2",
        },
        "message": "User message for week 2",
    }

    ingest_request(user.id, input_data)

    new_session = user.sessions.order_by("-created_at").first()
    assert new_session != session
    assert new_session.week_number == 2
    assert new_session.initial_message == "Initial Hello From Week 2"

    transcripts = ChatTranscript.objects.filter(session__user=user).order_by("id")
    assert transcripts.count() == 3  # 2 existing + 1 new assistant
    assert transcripts.last().role == "user"
    assert transcripts.last().content == "User message for week 2"


def test_existing_user_no_update(existing_user, existing_transcript):
    """
    When an existing user sends unchanged context data,
    only a new transcript entry should be created.
    """
    user, session = existing_user
    input_data = {
        "context": {
            "week_number": 1,
            "initial_message": "Initial Hello",
            "message_type": MessageType.SUMMARY,
        },
        "message": "Just another message",
    }

    ingest_request(user.id, input_data)

    new_session = user.sessions.order_by("-created_at").first()
    assert new_session == session

    transcripts = ChatTranscript.objects.filter(session__user=user).order_by("id")
    assert transcripts.count() == 2
    assert transcripts.last().role == "user"
    assert transcripts.last().content == "Just another message"
