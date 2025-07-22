import pytest
from chat.models import BaseChatTranscript, IndividualSession, MessageType, User, IndividualChatTranscript
from chat.serializers import IndividualIncomingMessageSerializer
from chat.services.individual_crud import ingest_request


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


@pytest.fixture
def make_input_data(base_context):
    def _make(overrides=None, message=""):
        # if you ever have nested structures you want to override, switch to deepcopy
        ctx = base_context.copy()
        if overrides:
            ctx.update(overrides)
        return {
            "context": ctx,
            "message": message,
        }

    return _make


def test_new_user_creation(make_input_data):
    """
    When a user is not found, a new record should be created using context data,
    and two IndividualChatTranscript records should be generated.
    """
    participant_id = "new_user_1"
    input_data = make_input_data(message="I would like to enroll.")

    serializer = IndividualIncomingMessageSerializer(data=input_data)
    serializer.is_valid(raise_exception=True)
    individual_incoming_message = serializer.validated_data

    ingest_request(participant_id, individual_incoming_message)

    # Assert that the user was created with correct attributes
    user = User.objects.get(id=participant_id)
    session = user.sessions.order_by("-created_at").first()
    assert user.school_name == "Test High"
    assert user.school_mascot == "Tigers"
    assert user.name == "Alice"
    assert session.week_number == 1
    assert session.message_type == MessageType.INITIAL

    # Assert that two transcripts were created
    transcripts = IndividualChatTranscript.objects.filter(session=session).order_by("id")
    assert transcripts.count() == 2
    assert transcripts[0].role == BaseChatTranscript.Role.ASSISTANT
    assert transcripts[0].content == "Hello, world!"
    assert transcripts[1].role == BaseChatTranscript.Role.USER
    assert transcripts[1].content == "I would like to enroll."
    assert transcripts.first().week_number == 1
    assert transcripts.last().week_number == 1
    assert transcripts.first().school_name == "Test High"
    assert transcripts.last().school_name == "Test High"


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
        week_number=1,
        message_type=MessageType.SUMMARY,
    )

    return user, session


@pytest.fixture
def existing_transcript(existing_user):
    user, _ = existing_user
    return IndividualChatTranscript.objects.create(
        session=user.current_session,
        role=BaseChatTranscript.Role.ASSISTANT,
        content="Initial Hello",
        hub_initiated=True,
    )


@pytest.mark.parametrize("initial_message", ["some initial message", ""])
def test_existing_user_update_session_context(existing_user, existing_transcript, make_input_data, initial_message):
    """
    When an existing user sends data with a changed week_number,
    the user record should update and a new transcript entry should be added.
    """
    user, session = existing_user
    input_data = make_input_data(
        overrides={
            "week_number": 2,
            "message_type": MessageType.INITIAL,
            "initial_message": initial_message,
        },
        message="User message for week 2",
    )

    serializer = IndividualIncomingMessageSerializer(data=input_data)
    serializer.is_valid(raise_exception=True)
    individual_incoming_message = serializer.validated_data

    ingest_request(user.id, individual_incoming_message)

    new_session = user.sessions.order_by("-created_at").first()
    assert new_session != session
    assert new_session.week_number == 2

    transcripts = IndividualChatTranscript.objects.filter(session__user=user).order_by("id")
    if initial_message:
        assert transcripts.count() == 3  # 1 existing + 1 new assistant + 1 new user
    else:
        assert transcripts.count() == 2  # 1 existing + 1 new user (no assistant transcript)
    assert transcripts.last().role == "user"
    assert transcripts.last().content == "User message for week 2"


def test_existing_user_no_update(existing_user, existing_transcript, make_input_data):
    """
    When an existing user sends unchanged context data,
    only a new transcript entry should be created.
    """
    user, session = existing_user
    input_data = make_input_data(
        overrides={
            "week_number": 1,
            "message_type": MessageType.SUMMARY,
            "initial_message": "Initial Hello",
        },
        message="Just another message",
    )

    serializer = IndividualIncomingMessageSerializer(data=input_data)
    serializer.is_valid(raise_exception=True)
    individual_incoming_message = serializer.validated_data

    ingest_request(user.id, individual_incoming_message)

    new_session = user.sessions.order_by("-created_at").first()
    assert new_session == session

    transcripts = IndividualChatTranscript.objects.filter(session__user=user).order_by("id")
    assert transcripts.count() == 2
    assert transcripts.last().role == "user"
    assert transcripts.last().content == "Just another message"
