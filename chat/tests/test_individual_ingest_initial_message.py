import copy
import pytest
from django.urls import reverse

from chat.models import (
    BaseChatTranscript,
    IndividualChatTranscript,
    IndividualSession,
    MessageType,
    User,
)


@pytest.fixture
def base_individual_initial_message_payload():
    """Base payload for individual initial message requests"""
    return {
        "message": "Welcome to the individual chat!",
        "context": {
            "name": "Alice Johnson",
            "school_name": "Test High School",
            "school_mascot": "Eagles",
            "week_number": 1,
            "message_type": MessageType.INITIAL,
        },
    }


def test_ingest_individual_initial_message_success(
    message_client, celery_task_always_eager, base_individual_initial_message_payload
):
    """Test successful individual initial message ingestion creates user, session and transcript"""
    user_id = "alice123"
    url = reverse("chat:ingest-individual-initial", args=[user_id])

    response = message_client.post(
        url,
        base_individual_initial_message_payload,
        content_type="application/json",
    )

    assert response.status_code == 202
    assert response.json() == {"message": "Data received"}

    # Verify user was created
    user = User.objects.get(id=user_id)
    assert user.id == user_id
    assert user.name == "Alice Johnson"
    assert user.school_name == "Test High School"
    assert user.school_mascot == "Eagles"
    assert not user.is_test
    assert user.group is None  # Individual users don't belong to groups

    # Verify session was created
    session = IndividualSession.objects.get(user=user)
    assert session.week_number == 1
    assert session.message_type == MessageType.INITIAL

    # Verify initial message transcript was created
    transcripts = IndividualChatTranscript.objects.filter(session=session).order_by("created_at")
    assert transcripts.count() == 1
    initial_transcript = transcripts[0]
    assert initial_transcript.role == BaseChatTranscript.Role.ASSISTANT
    assert initial_transcript.content == "Welcome to the individual chat!"
    assert initial_transcript.hub_initiated is True


def test_ingest_individual_initial_message_creates_new_session_existing_user(
    message_client, celery_task_always_eager, base_individual_initial_message_payload
):
    """Test initial message for existing user creates new session for different week/message type"""
    user_id = "existing_alice"

    # Create existing user with session for different week
    existing_user = User.objects.create(
        id=user_id, name="Old Name", school_name="Old School", school_mascot="Old Mascot"
    )
    existing_session = IndividualSession.objects.create(
        user=existing_user, week_number=2, message_type=MessageType.INITIAL
    )

    url = reverse("chat:ingest-individual-initial", args=[user_id])

    response = message_client.post(
        url,
        base_individual_initial_message_payload,
        content_type="application/json",
    )

    assert response.status_code == 202

    # Verify user was updated with new information
    existing_user.refresh_from_db()
    assert existing_user.name == "Alice Johnson"
    assert existing_user.school_name == "Test High School"
    assert existing_user.school_mascot == "Eagles"

    # Verify new session was created for week 1
    sessions = IndividualSession.objects.filter(user=existing_user).order_by("week_number")
    assert sessions.count() == 2
    new_session = sessions[0]  # Week 1 session
    assert new_session.week_number == 1
    assert new_session.message_type == MessageType.INITIAL

    # Verify initial message transcript was created for new session
    transcripts = IndividualChatTranscript.objects.filter(session=new_session)
    assert transcripts.count() == 1
    assert transcripts[0].content == "Welcome to the individual chat!"


def test_ingest_individual_initial_message_duplicate_session(
    message_client, celery_task_always_eager, base_individual_initial_message_payload
):
    """Test initial message for duplicate session (same user, week, message_type)"""
    user_id = "duplicate_alice"

    # Create user and session first
    user = User.objects.create(id=user_id, name="Alice Johnson")
    existing_session = IndividualSession.objects.create(user=user, week_number=1, message_type=MessageType.INITIAL)

    url = reverse("chat:ingest-individual-initial", args=[user_id])

    response = message_client.post(
        url,
        base_individual_initial_message_payload,
        content_type="application/json",
    )

    assert response.status_code == 202

    # Verify only one session exists (get_or_create behavior)
    sessions = IndividualSession.objects.filter(user=user)
    assert sessions.count() == 1


def test_ingest_individual_initial_message_updates_existing_user(
    message_client, celery_task_always_eager, base_individual_initial_message_payload
):
    """Test initial message updates existing user with new information"""
    user_id = "update_alice"

    # Create existing user with outdated info
    existing_user = User.objects.create(
        id=user_id,
        name="Old Name",
        school_name="Old School",
        school_mascot="Old Mascot",
    )

    url = reverse("chat:ingest-individual-initial", args=[user_id])

    response = message_client.post(
        url,
        base_individual_initial_message_payload,
        content_type="application/json",
    )

    assert response.status_code == 202

    # Verify user was updated
    existing_user.refresh_from_db()
    assert existing_user.name == "Alice Johnson"
    assert existing_user.school_name == "Test High School"
    assert existing_user.school_mascot == "Eagles"

    # Verify session and transcript were created
    session = IndividualSession.objects.get(user=existing_user)
    transcripts = IndividualChatTranscript.objects.filter(session=session)
    assert transcripts.count() == 1


def test_ingest_individual_initial_message_invalid_payload(message_client, celery_task_always_eager):
    """Test initial message with invalid payload structure"""
    user_id = "invalid_alice"
    url = reverse("chat:ingest-individual-initial", args=[user_id])

    invalid_payload = {
        "context": {
            "name": "Alice",
            # Missing required fields like school_name, message_type, etc.
        }
    }

    response = message_client.post(
        url,
        invalid_payload,
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "context" in response.json()


def test_ingest_individual_initial_message_unauthorized(
    client, celery_task_always_eager, base_individual_initial_message_payload
):
    """Test initial message without proper authentication"""
    user_id = "auth_alice"
    url = reverse("chat:ingest-individual-initial", args=[user_id])

    # Use regular client without auth headers
    response = client.post(
        url,
        base_individual_initial_message_payload,
        content_type="application/json",
    )

    assert response.status_code == 403


@pytest.mark.parametrize("message_type", [MessageType.REMINDER, MessageType.SUMMARY, MessageType.CHECK_IN])
def test_ingest_individual_initial_message_different_message_types(
    message_client, celery_task_always_eager, base_individual_initial_message_payload, message_type
):
    """Test initial message ingestion with different valid message types for individuals"""
    user_id = f"test_user_{message_type}"
    payload = copy.deepcopy(base_individual_initial_message_payload)
    payload["context"]["message_type"] = message_type

    url = reverse("chat:ingest-individual-initial", args=[user_id])

    response = message_client.post(
        url,
        payload,
        content_type="application/json",
    )

    assert response.status_code == 202

    # Verify session was created with correct message type
    user = User.objects.get(id=user_id)
    session = IndividualSession.objects.get(user=user)
    assert session.message_type == message_type


def test_ingest_individual_initial_message_empty_message(
    message_client, celery_task_always_eager, base_individual_initial_message_payload
):
    """Test initial message with empty content"""
    user_id = "empty_alice"
    payload = copy.deepcopy(base_individual_initial_message_payload)
    payload["message"] = ""

    url = reverse("chat:ingest-individual-initial", args=[user_id])

    response = message_client.post(
        url,
        payload,
        content_type="application/json",
    )

    assert response.status_code == 400
