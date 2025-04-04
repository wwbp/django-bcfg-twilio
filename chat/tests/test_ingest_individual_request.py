import pytest
from chat.models import MessageType, User, ChatTranscript
from chat.services.crud import ingest_individual_request


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

    ingest_individual_request(participant_id, input_data)

    # Assert that the user was created with correct attributes
    user = User.objects.get(id=participant_id)
    assert user.school_name == "Test High"
    assert user.school_mascot == "Tigers"
    assert user.name == "Alice"
    assert user.initial_message == "Hello, world!"
    assert user.week_number == 1
    assert user.message_type == MessageType.INITIAL

    # Assert that two transcripts were created
    transcripts = ChatTranscript.objects.filter(user=user).order_by("id")
    assert transcripts.count() == 2
    assert transcripts[0].role == "assistant"
    assert transcripts[0].content == "Hello, world!"
    assert transcripts[1].role == "user"
    assert transcripts[1].content == "I would like to enroll."


@pytest.fixture
def existing_user():
    return User.objects.create(
        id="existing_week_update",
        school_name="Old School",
        school_mascot="Lions",
        name="Bob",
        initial_message="Initial Hello",
        week_number=1,
        message_type=MessageType.SUMMARY,
    )


@pytest.fixture
def existing_transcript(existing_user):
    return ChatTranscript.objects.create(user=existing_user, role="assistant", content="Initial Hello")


def test_existing_user_update_week_number(existing_user, existing_transcript):
    """
    When an existing user sends data with a changed week_number,
    the user record should update and a new transcript entry should be added.
    """
    input_data = {
        "context": {
            "week_number": 2,
        },
        "message": "User message for week 2",
    }

    ingest_individual_request(existing_user.id, input_data)

    existing_user.refresh_from_db()
    assert existing_user.week_number == 2
    assert existing_user.initial_message == "Initial Hello"

    transcripts = ChatTranscript.objects.filter(user=existing_user).order_by("id")
    assert transcripts.count() == 2
    assert transcripts.last().role == "user"
    assert transcripts.last().content == "User message for week 2"


def test_existing_user_update_initial_message(existing_user, existing_transcript):
    """
    When an existing user sends a new initial message in the context,
    the user record should update and create new transcripts.
    """
    input_data = {
        "context": {
            "initial_message": "New greeting",
        },
        "message": "Follow up message",
    }

    ingest_individual_request(existing_user.id, input_data)

    existing_user.refresh_from_db()
    assert existing_user.initial_message == "New greeting"

    transcripts = ChatTranscript.objects.filter(user=existing_user).order_by("id")
    assert transcripts.count() == 3
    assert transcripts[1].role == "assistant"
    assert transcripts[1].content == "New greeting"
    assert transcripts.last().role == "user"
    assert transcripts.last().content == "Follow up message"


def test_existing_user_update_message_type(existing_user, existing_transcript):
    """
    When an existing user sends a new message_type in the context,
    the user record should update accordingly and a new transcript entry should be added.
    """
    input_data = {
        "context": {
            "message_type": MessageType.CHECK_IN,
        },
        "message": "User check-in message",
    }

    ingest_individual_request(existing_user.id, input_data)

    existing_user.refresh_from_db()
    assert existing_user.message_type == MessageType.CHECK_IN

    transcripts = ChatTranscript.objects.filter(user=existing_user).order_by("id")
    assert transcripts.last().role == "user"
    assert transcripts.last().content == "User check-in message"


def test_existing_user_no_update(existing_user, existing_transcript):
    """
    When an existing user sends unchanged context data,
    only a new transcript entry should be created.
    """
    input_data = {
        "context": {
            "week_number": 1,
            "initial_message": "Initial Hello",
            "message_type": MessageType.SUMMARY,
        },
        "message": "Just another message",
    }

    ingest_individual_request(existing_user.id, input_data)

    existing_user.refresh_from_db()
    assert existing_user.week_number == 1
    assert existing_user.initial_message == "Initial Hello"
    assert existing_user.message_type == MessageType.SUMMARY

    transcripts = ChatTranscript.objects.filter(user=existing_user).order_by("id")
    assert transcripts.count() == 2
    assert transcripts.last().role == "user"
    assert transcripts.last().content == "Just another message"
