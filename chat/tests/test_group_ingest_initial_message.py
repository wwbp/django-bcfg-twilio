import copy
import logging
import pytest
from django.urls import reverse

from chat.models import (
    BaseChatTranscript,
    Group,
    GroupChatTranscript,
    GroupSession,
    GroupStrategyPhase,
    MessageType,
    User,
)


@pytest.fixture
def base_initial_message_payload():
    """Base payload for initial message requests"""
    return {
        "message": "Welcome to the group chat!",
        "context": {
            "school_name": "Test High School",
            "school_mascot": "Eagles",
            "week_number": 1,
            "message_type": MessageType.INITIAL,
            "participants": [
                {
                    "name": "Alice Johnson",
                    "id": "alice123",
                },
                {
                    "name": "Bob Smith",
                    "id": "bob456",
                },
            ],
        },
    }


def test_ingest_group_initial_message_success(message_client, celery_task_always_eager, base_initial_message_payload):
    """Test successful initial message ingestion creates group, users, session and transcript"""
    group_id = "test_group_123"
    url = reverse("chat:ingest-group-initial", args=[group_id])

    response = message_client.post(
        url,
        base_initial_message_payload,
        content_type="application/json",
    )

    assert response.status_code == 202
    assert response.json() == {"message": "Data received"}

    # Verify group was created
    group = Group.objects.get(id=group_id)
    assert group.id == group_id
    assert not group.is_test

    # Verify users were created and added to group
    users = User.objects.filter(group=group).order_by("id")
    assert users.count() == 2
    assert users[0].id == "alice123"
    assert users[0].name == "Alice Johnson"
    assert users[0].school_name == "Test High School"
    assert users[0].school_mascot == "Eagles"
    assert users[1].id == "bob456"
    assert users[1].name == "Bob Smith"

    # Verify session was created
    session = GroupSession.objects.get(group=group)
    assert session.week_number == 1
    assert session.message_type == MessageType.INITIAL
    assert session.current_strategy_phase == GroupStrategyPhase.BEFORE_AUDIENCE

    # Verify initial message transcript was created
    transcripts = GroupChatTranscript.objects.filter(session=session).order_by("created_at")
    assert transcripts.count() == 1
    initial_transcript = transcripts[0]
    assert initial_transcript.role == BaseChatTranscript.Role.ASSISTANT
    assert initial_transcript.content == "Welcome to the group chat!"
    assert initial_transcript.hub_initiated is True
    assert initial_transcript.assistant_strategy_phase == GroupStrategyPhase.AUDIENCE


def test_ingest_group_initial_message_creates_existing_group_new_session(
    message_client, celery_task_always_eager, base_initial_message_payload
):
    """Test initial message for existing group creates new session"""
    group_id = "existing_group"

    # Create existing group with user
    existing_group = Group.objects.create(id=group_id)
    existing_user = User.objects.create(
        id="existing_user", group=existing_group, name="Existing User", school_name="Old School"
    )

    # Create existing session for different week
    existing_session = GroupSession.objects.create(
        group=existing_group, week_number=2, message_type=MessageType.INITIAL
    )

    url = reverse("chat:ingest-group-initial", args=[group_id])

    response = message_client.post(
        url,
        base_initial_message_payload,
        content_type="application/json",
    )

    assert response.status_code == 202

    # Verify new session was created for week 1
    sessions = GroupSession.objects.filter(group=existing_group).order_by("week_number")
    assert sessions.count() == 2
    new_session = sessions[0]  # Week 1 session
    assert new_session.week_number == 1
    assert new_session.message_type == MessageType.INITIAL

    # Verify users were updated with new participants
    users = User.objects.filter(group=existing_group).order_by("id")
    assert users.count() == 2  # existing_user was removed, new participants added
    assert "alice123" in [u.id for u in users]
    assert "bob456" in [u.id for u in users]


def test_ingest_group_initial_message_updates_existing_users(
    message_client, celery_task_always_eager, base_initial_message_payload
):
    """Test initial message updates existing users with new information"""
    group_id = "test_group_456"

    # Create existing group and user with outdated info
    existing_group = Group.objects.create(id=group_id)
    existing_user = User.objects.create(
        id="alice123",  # Same ID as in payload
        group=existing_group,
        name="Old Name",
        school_name="Old School",
        school_mascot="Old Mascot",
    )

    url = reverse("chat:ingest-group-initial", args=[group_id])

    response = message_client.post(
        url,
        base_initial_message_payload,
        content_type="application/json",
    )

    assert response.status_code == 202

    # Verify user was updated
    existing_user.refresh_from_db()
    assert existing_user.name == "Alice Johnson"
    assert existing_user.school_name == "Test High School"
    assert existing_user.school_mascot == "Eagles"

    # Verify new user was created
    users = User.objects.filter(group=existing_group).order_by("id")
    assert users.count() == 2
    bob_user = users.get(id="bob456")
    assert bob_user.name == "Bob Smith"


def test_ingest_group_initial_message_invalid_message_type(
    message_client, celery_task_always_eager, base_initial_message_payload, caplog
):
    """Test initial message ingestion with invalid message type"""
    group_id = "test_group_invalid"
    payload = copy.deepcopy(base_initial_message_payload)
    payload["context"]["message_type"] = MessageType.CHECK_IN  # Invalid for groups

    url = reverse("chat:ingest-group-initial", args=[group_id])

    response = message_client.post(
        url,
        payload,
        content_type="application/json",
    )

    # Should still return 202 but log error
    assert response.status_code == 202
    assert "Group session cannot be of type" in caplog.text
    assert GroupChatTranscript.objects.count() == 0


def test_ingest_group_initial_message_duplicate_session(
    message_client, celery_task_always_eager, base_initial_message_payload
):
    """Test initial message for duplicate session (same group, week, message_type)"""
    group_id = "duplicate_group"

    # Create group and session first
    group = Group.objects.create(id=group_id)
    existing_session = GroupSession.objects.create(group=group, week_number=1, message_type=MessageType.INITIAL)

    url = reverse("chat:ingest-group-initial", args=[group_id])

    response = message_client.post(
        url,
        base_initial_message_payload,
        content_type="application/json",
    )

    assert response.status_code == 202

    # Verify only one session exists (get_or_create behavior)
    sessions = GroupSession.objects.filter(group=group)
    assert sessions.count() == 1


def test_ingest_group_initial_message_removes_old_participants(
    message_client, celery_task_always_eager, base_initial_message_payload, caplog
):
    """Test that users not in participants list are removed from group"""
    caplog.set_level(logging.INFO)
    group_id = "removal_group"

    # Create group with extra user not in new participants list
    group = Group.objects.create(id=group_id)
    User.objects.create(id="alice123", group=group, name="Alice Johnson", school_name="Test High School")
    User.objects.create(
        id="old_user",  # Not in new participants list
        group=group,
        name="Old User",
        school_name="Test High School",
    )

    url = reverse("chat:ingest-group-initial", args=[group_id])

    response = message_client.post(
        url,
        base_initial_message_payload,
        content_type="application/json",
    )

    assert response.status_code == 202

    # Verify old user was removed from group
    users_in_group = User.objects.filter(group=group)
    user_ids = [u.id for u in users_in_group]
    assert "old_user" not in user_ids
    assert "alice123" in user_ids
    assert "bob456" in user_ids

    # Verify user still exists but not in group
    old_user = User.objects.get(id="old_user")
    assert old_user.group is None

    assert "Removing user old_user from group removal_group" in caplog.text


def test_ingest_group_initial_message_invalid_payload(message_client, celery_task_always_eager):
    """Test initial message with invalid payload structure"""
    group_id = "invalid_group"
    url = reverse("chat:ingest-group-initial", args=[group_id])

    invalid_payload = {
        "context": {
            "school_name": "Test School",
            # Missing required fields
        }
    }

    response = message_client.post(
        url,
        invalid_payload,
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "context" in response.json()


def test_ingest_group_initial_message_unauthorized(client, celery_task_always_eager, base_initial_message_payload):
    """Test initial message without proper authentication"""
    group_id = "auth_test_group"
    url = reverse("chat:ingest-group-initial", args=[group_id])

    # Use regular client without auth headers
    response = client.post(
        url,
        base_initial_message_payload,
        content_type="application/json",
    )

    assert response.status_code == 403


@pytest.mark.parametrize("message_type", [MessageType.REMINDER, MessageType.SUMMARY])
def test_ingest_group_initial_message_different_message_types(
    message_client, celery_task_always_eager, base_initial_message_payload, message_type
):
    """Test initial message ingestion with different valid message types"""
    group_id = f"test_group_{message_type}"
    payload = copy.deepcopy(base_initial_message_payload)
    payload["context"]["message_type"] = message_type

    url = reverse("chat:ingest-group-initial", args=[group_id])

    response = message_client.post(
        url,
        payload,
        content_type="application/json",
    )

    assert response.status_code == 202

    # Verify session was created with correct message type
    group = Group.objects.get(id=group_id)
    session = GroupSession.objects.get(group=group)
    assert session.message_type == message_type
