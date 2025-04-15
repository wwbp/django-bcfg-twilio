import copy
import logging
from uuid import uuid4
from django.test import override_settings
from django.urls import reverse
import pytest

from chat.models import BaseChatTranscript, Control, Group, GroupPipelineRecord, GroupSession, MessageType, Prompt, User

_INITIAL_MESSAGE = "Some initial message"
_FIRST_USER_MESSAGE = "some message from user"
_VALID_API_KEY = "valid-api-key"


@pytest.fixture
def inbound_call_and_mocks():
    group_id = str(uuid4())
    sender_id = str(uuid4())
    other_user1_id = str(uuid4())
    other_user2_id = str(uuid4())
    other_user3_id = str(uuid4())
    inbound_payload = {
        "message": _FIRST_USER_MESSAGE,
        "sender_id": sender_id,
        "context": {
            "school_name": "Test School",
            "school_mascot": "Test Mascot",
            "initial_message": _INITIAL_MESSAGE,
            "week_number": 1,
            "message_type": MessageType.INITIAL,
            "participants": [
                {
                    "name": "Participant 1",
                    "id": sender_id,
                },
                {
                    "name": "Participant 2",
                    "id": other_user1_id,
                },
                {
                    "name": "Participant 3",
                    "id": other_user2_id,
                },
                {
                    "name": "Participant 4",
                    "id": other_user3_id,
                },
            ],
        },
    }
    Prompt.objects.create(
        is_for_group=True,
        week=inbound_payload["context"]["week_number"],
        type=inbound_payload["context"]["message_type"],
        activity="base activity",
    )
    Control.objects.create(system="System", persona="Persona")
    return group_id, sender_id, inbound_payload, other_user1_id, other_user2_id, other_user3_id


@override_settings(INBOUND_MESSAGE_API_KEY=_VALID_API_KEY)
def test_group_pipeline(inbound_call_and_mocks, celery_task_always_eager, client, caplog):
    caplog.set_level(logging.INFO)
    group_id, sender_id, data, _, _, _ = inbound_call_and_mocks
    url = reverse("chat:ingest-group", args=[group_id])

    response = client.post(
        url,
        data,
        content_type="application/json",
        headers={"Authorization": f"Bearer {_VALID_API_KEY}"},
    )
    assert response.status_code == 202

    record = GroupPipelineRecord.objects.get()
    assert record.group.id == group_id
    assert record.user.id == sender_id
    assert record.message == _FIRST_USER_MESSAGE

    session = GroupSession.objects.get()
    assert session == record.group.current_session
    assert session.initial_message == _INITIAL_MESSAGE
    transcripts = list(session.transcripts.order_by("created_at").all())
    assert len(transcripts) == 2
    assert transcripts[0].role == BaseChatTranscript.Role.ASSISTANT
    assert transcripts[0].content == _INITIAL_MESSAGE
    assert transcripts[1].role == BaseChatTranscript.Role.USER
    assert transcripts[1].content == _FIRST_USER_MESSAGE

    assert Group.objects.count() == 1
    users = list(User.objects.all())
    assert len(users) == 4
    assert all(user.group == record.group for user in users)
    assert all(user.school_mascot == data["context"]["school_mascot"] for user in users)
    assert all(user.school_name == data["context"]["school_name"] for user in users)
    for user in users:
        matching_payload_participant = next(
            participant for participant in data["context"]["participants"] if participant["id"] == user.id
        )
        assert matching_payload_participant["name"] == user.name

    # now send a second message, group and session exist and are reused
    second_message_data = copy.deepcopy(data)
    second_message_data["message"] = "some other message from user"
    response = client.post(
        url,
        data,
        content_type="application/json",
        headers={"Authorization": f"Bearer {_VALID_API_KEY}"},
    )
    assert response.status_code == 202
    records = list(GroupPipelineRecord.objects.order_by("created_at").all())
    assert len(records) == 2
    assert records[0].id == record.id
    assert Group.objects.count() == 1
    users = list(User.objects.all())
    assert len(users) == 4
    assert "is already in group" not in caplog.text
    assert "Removing user" not in caplog.text
    assert "Existing group does not yet have user" not in caplog.text


@override_settings(INBOUND_MESSAGE_API_KEY=_VALID_API_KEY)
def test_group_pipeline_participants_changed(inbound_call_and_mocks, celery_task_always_eager, client, caplog):
    caplog.set_level(logging.INFO)
    group_id, sender_id, data, other_user1_id, other_user2_id, other_user3_id = inbound_call_and_mocks
    url = reverse("chat:ingest-group", args=[group_id])

    # sender user is already in group, other_user1 is in another group, other_user2 does not yet exist
    existing_group = Group.objects.create(id=group_id)
    other_group = Group.objects.create(id=str(uuid4()))
    sender_user = User.objects.create(
        id=sender_id,
        group=existing_group,
        name="Participant 1",
        school_name=data["context"]["school_name"],
        school_mascot=data["context"]["school_mascot"],
    )
    user_to_be_moved_to_group = User.objects.create(
        id=other_user1_id,
        group=other_group,
        name="Participant 2",
        school_name=data["context"]["school_name"],
        school_mascot=data["context"]["school_mascot"],
    )
    user_to_be_removed_from_group = User.objects.create(
        id=str(uuid4()), group=existing_group, name="Removed Participant"
    )
    unrelated_other_user = User.objects.create(id=str(uuid4()), name="Unrelated User")
    user_to_be_created_id = other_user2_id
    user_to_be_updated_in_group = User.objects.create(
        id=other_user3_id,
        group=existing_group,
        name="Participant 4",
        school_name="School to be updated",
        school_mascot=data["context"]["school_mascot"],
    )

    response = client.post(
        url,
        data,
        content_type="application/json",
        headers={"Authorization": f"Bearer {_VALID_API_KEY}"},
    )

    assert response.status_code == 202
    assert f"User {user_to_be_moved_to_group.id} is already in group {other_group.id}" in caplog.text
    assert f"Existing group does not yet have user {user_to_be_created_id}" in caplog.text
    assert f"Removing user {user_to_be_removed_from_group.id} from group {existing_group.id}" in caplog.text
    assert unrelated_other_user.id not in caplog.text
    assert sender_user.id not in caplog.text
    existing_group.refresh_from_db()
    assert existing_group.users.count() == 4
    assert {user_to_be_moved_to_group.id, user_to_be_created_id, sender_user.id, user_to_be_updated_in_group.id} == set(
        user.id for user in existing_group.users.all()
    )
    assert Group.objects.count() == 2
    assert User.objects.count() == 6

    # confirm user attributes changed as needed
    user_to_be_updated_in_group.refresh_from_db()
    sender_user.refresh_from_db()
    assert user_to_be_updated_in_group.school_name == data["context"]["school_name"]
    assert user_to_be_updated_in_group.history.count() == 2  # 1 for creation, 1 for update
    assert sender_user.history.count() == 1  # no change needed so just creation,


@override_settings(INBOUND_MESSAGE_API_KEY=_VALID_API_KEY)
def test_group_pipeline_sender_not_in_participant_list(
    inbound_call_and_mocks, celery_task_always_eager, client, caplog
):
    group_id, _, data, _, _, _ = inbound_call_and_mocks
    url = reverse("chat:ingest-group", args=[group_id])
    new_sender_id = str(uuid4())
    data["sender_id"] = new_sender_id

    response = client.post(
        url,
        data,
        content_type="application/json",
        headers={"Authorization": f"Bearer {_VALID_API_KEY}"},
    )

    assert response.status_code == 202
    assert f"Group pipeline failed for group {group_id}" in caplog.text
    assert f"Sender ID {new_sender_id} not found in the list of participants" in caplog.text
    assert GroupPipelineRecord.objects.count() == 0


@override_settings(INBOUND_MESSAGE_API_KEY=_VALID_API_KEY)
def test_group_pipeline_invalid_message_type(inbound_call_and_mocks, celery_task_always_eager, client, caplog):
    group_id, _, data, _, _, _ = inbound_call_and_mocks
    url = reverse("chat:ingest-group", args=[group_id])
    data["context"]["message_type"] = MessageType.CHECK_IN.value

    response = client.post(
        url,
        data,
        content_type="application/json",
        headers={"Authorization": f"Bearer {_VALID_API_KEY}"},
    )

    assert response.status_code == 202
    assert f"Group pipeline failed for group {group_id}" in caplog.text
    assert "Group session cannot be of type" in caplog.text
    assert GroupPipelineRecord.objects.count() == 0


@override_settings(INBOUND_MESSAGE_API_KEY=_VALID_API_KEY)
def test_group_pipeline_changed_initial_message(inbound_call_and_mocks, celery_task_always_eager, client, caplog):
    group_id, _, data, _, _, _ = inbound_call_and_mocks
    url = reverse("chat:ingest-group", args=[group_id])

    # send initial message as before
    response = client.post(
        url,
        data,
        content_type="application/json",
        headers={"Authorization": f"Bearer {_VALID_API_KEY}"},
    )
    assert response.status_code == 202
    session = GroupSession.objects.get()
    assert session.initial_message == _INITIAL_MESSAGE

    # send a second message with different initial message
    new_initial_message_data = copy.deepcopy(data)
    new_initial_message_data["context"]["initial_message"] = "New initial message"
    response = client.post(
        url,
        new_initial_message_data,
        content_type="application/json",
        headers={"Authorization": f"Bearer {_VALID_API_KEY}"},
    )
    assert response.status_code == 202
    session = GroupSession.objects.get()
    assert session.initial_message == _INITIAL_MESSAGE
    assert "Got new initial_message for existing group session" in caplog.text
