import copy
import json
import logging
from unittest.mock import patch
from uuid import uuid4
from django.urls import reverse
from django.utils import timezone
import pytest

from chat.models import (
    BaseChatTranscript,
    ControlConfig,
    Group,
    GroupChatTranscript,
    GroupPipelineRecord,
    GroupScheduledTaskAssociation,
    GroupSession,
    GroupStrategyPhase,
    GroupStrategyPhaseConfig,
    MessageType,
    User,
)
from chat.serializers import GroupIncomingMessageSerializer
from config import celery
from chat.services.group_pipeline import _FALLBACK_DELAY_WITHOUT_CONFIG_SECONDS, _ingest

_INITIAL_MESSAGE = "Some initial message"
_FIRST_USER_MESSAGE = "some message from user"


@pytest.fixture
def _inbound_call(control_config_factory):
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

    control_config_factory(key=ControlConfig.ControlConfigKey.GROUP_AUDIENCE_STRATEGY_PROMPT, value="base activity")
    control_config_factory(key=ControlConfig.ControlConfigKey.PERSONA_PROMPT, value="test persona prompt")
    control_config_factory(key=ControlConfig.ControlConfigKey.SYSTEM_PROMPT, value="test system prompt")
    control_config_factory(
        key=ControlConfig.ControlConfigKey.GROUP_INSTRUCTION_PROMPT_TEMPLATE,
        value=(
            "Using the below system prompt as your guide, engage with the group as a participant in a "
            "manner that reflects your assigned persona and follows the conversation stategy instructions"
            "System Prompt: {system}\n\n"
            "Assigned Persona: {persona}\n\n"
            "Assistant Name: {assistant_name}\n\n"
            "Group's School: {school_name}\n\n"
            "Strategy: {strategy}\n\n"
        ),
    )

    yield group_id, sender_id, inbound_payload, other_user1_id, other_user2_id, other_user3_id


@pytest.fixture
def _mocks():
    with (
        patch("chat.services.group_pipeline.moderate_message", return_value="") as mock_moderate_message,
        patch(
            "chat.services.group_pipeline.send_moderation_message", return_value={"status": "ok"}
        ) as mock_send_moderation_message,
        patch(
            "chat.services.group_pipeline.send_message_to_participant_group", return_value={"status": "ok"}
        ) as mock_send_message_to_participant,
        patch(
            "chat.services.completion._generate_response", return_value=("Some LLM response", None, None)
        ) as mock_generate_response,
    ):
        yield (
            mock_moderate_message,
            mock_send_moderation_message,
            mock_send_message_to_participant,
            mock_generate_response,
        )


@pytest.mark.parametrize("moderated", [True, False])
def test_group_pipeline_handle_inbound_message(
    _inbound_call, _mocks, celery_task_always_eager, message_client, caplog, moderated
):
    # arrange
    group_id, sender_id, data, _, _, _ = _inbound_call
    mock_moderate_message, mock_send_moderation_message, mock_send_message_to_participant, mock_generate_response = (
        _mocks
    )
    if moderated:
        mock_moderate_message.return_value = "Blocked message"
    caplog.set_level(logging.INFO)
    url = reverse("chat:ingest-group", args=[group_id])

    # act
    response = message_client.post(
        url,
        data,
        content_type="application/json",
    )

    # assert response
    assert response.status_code == 202

    # assert pipeline record
    record = GroupPipelineRecord.objects.get()
    assert record.group.id == group_id
    assert record.user.id == sender_id
    assert record.message == _FIRST_USER_MESSAGE
    if moderated:
        assert record.status == GroupPipelineRecord.StageStatus.MODERATION_BLOCKED
        assert mock_send_moderation_message.call_count == 1
        assert mock_generate_response.call_count == 0
    else:
        assert record.status == GroupPipelineRecord.StageStatus.SCHEDULED_ACTION
        assert mock_send_moderation_message.call_count == 0

    # assert session and transcript
    session = GroupSession.objects.get()
    assert session == record.group.current_session
    assert session.initial_message == _INITIAL_MESSAGE
    assert session.current_strategy_phase == GroupStrategyPhase.BEFORE_AUDIENCE
    transcripts = list(session.transcripts.order_by("created_at").all())
    assert len(transcripts) == 2
    assert transcripts[0].role == BaseChatTranscript.Role.ASSISTANT
    assert transcripts[0].content == _INITIAL_MESSAGE
    assert transcripts[1].role == BaseChatTranscript.Role.USER
    assert transcripts[1].content == _FIRST_USER_MESSAGE

    # assert group and users
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

    # assert expected task is created, will execute in 1 to 5 minutes from now, and then force execute it now
    if not moderated:
        assert GroupScheduledTaskAssociation.objects.count() == 1
        assert GroupScheduledTaskAssociation.objects.first().group == record.group
        task = GroupScheduledTaskAssociation.objects.first().task
        scheduled_time = task.clocked.clocked_time
        assert scheduled_time > timezone.now() + timezone.timedelta(seconds=59)
        assert scheduled_time < timezone.now() + timezone.timedelta(seconds=300)
        task_function = celery.app.tasks[task.task]
        args = json.loads(task.args)
        kwargs = json.loads(task.kwargs)

        task_function.apply_async(args=args, kwargs=kwargs)
        assert mock_generate_response.call_count == 1
        record.refresh_from_db()
        session.refresh_from_db()
        assert "Group action complete for group" in caplog.text
        assert mock_send_message_to_participant.call_count == 1
        assert record.status == GroupPipelineRecord.StageStatus.SCHEDULED_ACTION
        assert session.current_strategy_phase == GroupStrategyPhase.AFTER_AUDIENCE
        transcripts = list(session.transcripts.order_by("created_at").all())
        assert len(transcripts) == 3
        assert transcripts[2].role == BaseChatTranscript.Role.ASSISTANT
        assert transcripts[2].content == "Some LLM response"
        assert transcripts[2].assistant_strategy_phase == GroupStrategyPhase.AUDIENCE

    # Finally, send a second message, group and session exist and are reused
    second_message_data = copy.deepcopy(data)
    second_message_data["message"] = "some other message from user"
    response = message_client.post(
        url,
        data,
        content_type="application/json",
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


def test_group_pipeline_handle_inbound_message_participants_changed(
    _inbound_call, _mocks, celery_task_always_eager, message_client, caplog
):
    caplog.set_level(logging.INFO)
    group_id, sender_id, data, other_user1_id, other_user2_id, other_user3_id = _inbound_call
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

    response = message_client.post(
        url,
        data,
        content_type="application/json",
    )

    assert response.status_code == 202
    assert f"User {user_to_be_moved_to_group.id} is already in group {other_group.id}" in caplog.text
    assert f"Existing group does not yet have user {user_to_be_created_id}" in caplog.text
    assert f"Removing user {user_to_be_removed_from_group.id} from group {existing_group.id}" in caplog.text
    assert unrelated_other_user.id not in caplog.text
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


def test_group_pipeline_handle_inbound_message_sender_not_in_participant_list(
    _inbound_call, _mocks, celery_task_always_eager, message_client, caplog
):
    group_id, _, data, _, _, _ = _inbound_call
    url = reverse("chat:ingest-group", args=[group_id])
    new_sender_id = str(uuid4())
    data["sender_id"] = new_sender_id

    response = message_client.post(
        url,
        data,
        content_type="application/json",
    )

    assert response.status_code == 202
    assert f"Group pipeline ingestion failed for group {group_id}" in caplog.text
    assert f"Sender ID {new_sender_id} not found in the list of participants" in caplog.text
    assert GroupPipelineRecord.objects.count() == 0
    assert GroupScheduledTaskAssociation.objects.count() == 0


def test_group_pipeline_handle_inbound_message_invalid_message_type(
    _inbound_call, _mocks, celery_task_always_eager, message_client, caplog
):
    group_id, _, data, _, _, _ = _inbound_call
    url = reverse("chat:ingest-group", args=[group_id])
    data["context"]["message_type"] = MessageType.CHECK_IN.value

    response = message_client.post(
        url,
        data,
        content_type="application/json",
    )

    assert response.status_code == 202
    assert f"Group pipeline ingestion failed for group {group_id}" in caplog.text
    assert "Group session cannot be of type" in caplog.text
    assert GroupPipelineRecord.objects.count() == 0
    assert GroupScheduledTaskAssociation.objects.count() == 0


def test_group_pipeline_handle_inbound_message_changed_initial_message(
    _inbound_call, _mocks, celery_task_always_eager, message_client, caplog
):
    group_id, _, data, _, _, _ = _inbound_call
    url = reverse("chat:ingest-group", args=[group_id])

    # send initial message as before
    response = message_client.post(
        url,
        data,
        content_type="application/json",
    )
    assert response.status_code == 202
    session = GroupSession.objects.get()
    assert session.initial_message == _INITIAL_MESSAGE

    # send a second message with different initial message
    new_initial_message_data = copy.deepcopy(data)
    new_initial_message_data["context"]["initial_message"] = "New initial message"
    response = message_client.post(
        url,
        new_initial_message_data,
        content_type="application/json",
    )
    assert response.status_code == 202
    session = GroupSession.objects.get()
    assert session.initial_message == _INITIAL_MESSAGE
    assert "Got new initial_message for existing group session" in caplog.text


def test_group_pipeline_handle_inbound_message_changed_empty_initial_message(
    _inbound_call, _mocks, celery_task_always_eager, message_client, caplog
):
    group_id, _, data, _, _, _ = _inbound_call
    url = reverse("chat:ingest-group", args=[group_id])

    # send initial message as before
    data["context"]["initial_message"] = ""
    response = message_client.post(
        url,
        data,
        content_type="application/json",
    )
    assert response.status_code == 202
    session = GroupSession.objects.get()
    assert session.initial_message == ""
    transcripts = session.transcripts
    assert transcripts.count() == 1
    assert transcripts.first().content == _FIRST_USER_MESSAGE


def test_group_pipeline_handle_inbound_message_throws_exception_after_ingest(
    _inbound_call, _mocks, celery_task_always_eager, message_client, caplog
):
    group_id, _, data, _, _, _ = _inbound_call
    url = reverse("chat:ingest-group", args=[group_id])
    mock_moderate_message, _, mock_send_message_to_participant, _ = _mocks
    mock_moderate_message.side_effect = Exception("Some error")

    # send initial message as before
    response = message_client.post(
        url,
        data,
        content_type="application/json",
    )
    assert response.status_code == 202
    record = GroupPipelineRecord.objects.get()
    assert record.status == GroupPipelineRecord.StageStatus.FAILED
    assert record.error_log == "Some error"
    assert "Group pipeline ingestion failed for group" in caplog.text
    assert "Some error" in caplog.text
    assert GroupScheduledTaskAssociation.objects.count() == 0


def test_group_pipeline_handle_inbound_message_clears_existing_scheduled_message(
    _inbound_call, _mocks, message_client, celery_task_always_eager
):
    group_id, _, data, _, _, _ = _inbound_call
    url = reverse("chat:ingest-group", args=[group_id])

    # send message, first task scheduled
    response = message_client.post(
        url,
        data,
        content_type="application/json",
    )
    assert response.status_code == 202
    record = GroupPipelineRecord.objects.get()
    task_association = GroupScheduledTaskAssociation.objects.get()
    assert json.loads(task_association.task.kwargs)["run_id"] == str(record.run_id)

    # send another message, second task scheduled, first task deleted
    response = message_client.post(
        url,
        data,
        content_type="application/json",
    )
    assert response.status_code == 202
    records = list(GroupPipelineRecord.objects.order_by("created_at").all())
    assert len(records) == 2
    assert records[0].id == record.id
    new_record = records[1]
    task_association = GroupScheduledTaskAssociation.objects.get()
    assert json.loads(task_association.task.kwargs)["run_id"] == str(new_record.run_id)


def test_group_pipeline_handle_inbound_message_new_message_during_ingestion(
    _inbound_call, _mocks, message_client, celery_task_always_eager
):
    group_id, sender_id, data, second_sender_id, _, _ = _inbound_call
    mock_moderate_message, _, mock_send_message_to_participant, _ = _mocks
    url = reverse("chat:ingest-group", args=[group_id])
    second_payload = copy.deepcopy(data)
    second_payload["message"] = "some message from user during first moderation"
    second_payload["sender_id"] = second_sender_id

    def mock_moderate_message_side_effect(*args, **kwargs):
        # mock another message is ingested here
        serializer = GroupIncomingMessageSerializer(data=second_payload)
        serializer.is_valid(raise_exception=True)
        _ingest(group_id, serializer.validated_data)
        return ""

    mock_moderate_message.side_effect = mock_moderate_message_side_effect

    response = message_client.post(
        url,
        data,
        content_type="application/json",
    )
    assert response.status_code == 202

    records = list(GroupPipelineRecord.objects.order_by("created_at").all())
    assert len(records) == 2
    assert all(record.group.id == str(group_id) for record in records)
    assert records[0].status == GroupPipelineRecord.StageStatus.PROCESS_SKIPPED
    assert records[1].status == GroupPipelineRecord.StageStatus.INGEST_PASSED
    assert records[0].user.id == sender_id
    assert records[1].user.id == second_sender_id
    transcripts = list(GroupChatTranscript.objects.order_by("created_at").all())
    assert len(transcripts) == 3
    assert transcripts[0].content == _INITIAL_MESSAGE
    assert transcripts[1].content == _FIRST_USER_MESSAGE
    assert transcripts[2].content == "some message from user during first moderation"
    assert all(t.week_number == 1 for t in transcripts)
    assert all(t.school_name == "Test School" for t in transcripts)


@pytest.mark.parametrize(
    "current_strategy_phase",
    [
        GroupStrategyPhase.BEFORE_AUDIENCE,
        GroupStrategyPhase.AFTER_AUDIENCE,
        GroupStrategyPhase.AFTER_REMINDER,
        GroupStrategyPhase.AFTER_FOLLOWUP,
        GroupStrategyPhase.AFTER_SUMMARY,
    ],
)
def test_group_pipeline_handle_inbound_message_updates_strategy_phase(
    _mocks, message_client, celery_task_always_eager, current_strategy_phase, group_with_initial_message_interaction
):
    group, session, _, example_message_context = group_with_initial_message_interaction
    url = reverse("chat:ingest-group", args=[group.id])
    session.current_strategy_phase = current_strategy_phase
    session.save()
    inbound_payload = {
        "message": "some next message from user",
        "sender_id": group.users.first().id,
        "context": example_message_context,
    }

    # send another message, second task scheduled, first task deleted
    response = message_client.post(
        url,
        inbound_payload,
        content_type="application/json",
    )

    assert response.status_code == 202
    pipeline_records = GroupPipelineRecord.objects.order_by("created_at").all()
    assert len(pipeline_records) == 2
    created_record = pipeline_records[1]
    assert created_record.status == GroupPipelineRecord.StageStatus.SCHEDULED_ACTION
    session.refresh_from_db()
    assert session.transcripts.count() == 4  # add one message or inbound
    # when we receive a message, we always revert to BEFORE_AUDIENCE phase
    # unless we are in AFTER_AUDIENCE phase, then we stay there
    if current_strategy_phase == GroupStrategyPhase.AFTER_AUDIENCE:
        assert session.current_strategy_phase == current_strategy_phase
    else:
        assert session.current_strategy_phase == GroupStrategyPhase.BEFORE_AUDIENCE


@pytest.mark.parametrize(
    "min_delay,max_delay,is_test", [[1, 3, False], [10, 10, False], [None, None, False], [100, 100, True]]
)
def test_group_pipeline_handle_inbound_message_delays_correct_duration(
    _mocks,
    message_client,
    celery_task_always_eager,
    group_with_initial_message_interaction,
    min_delay,
    max_delay,
    is_test,
    caplog,
):
    GroupStrategyPhaseConfig.objects.all().delete()
    current_phase = GroupStrategyPhase.BEFORE_AUDIENCE
    if min_delay:
        GroupStrategyPhaseConfig.objects.create(
            group_strategy_phase=current_phase,
            min_wait_seconds=min_delay,
            max_wait_seconds=max_delay,
        )

    group, session, _, example_message_context = group_with_initial_message_interaction
    if is_test:
        group.is_test = True
        group.save()
        for user in group.users.all():
            user.is_test = True
            user.save()
    url = reverse("chat:ingest-group", args=[group.id])
    session.current_strategy_phase = current_phase
    session.save()
    inbound_payload = {
        "message": "some next message from user",
        "sender_id": group.users.first().id,
        "context": example_message_context,
    }

    response = message_client.post(
        url,
        inbound_payload,
        content_type="application/json",
    )

    assert response.status_code == 202
    task = GroupScheduledTaskAssociation.objects.get().task
    clocked_time = task.clocked.clocked_time
    if is_test:
        assert clocked_time > timezone.now()
        assert clocked_time <= timezone.now() + timezone.timedelta(seconds=1)
    elif min_delay:
        assert clocked_time > timezone.now() + timezone.timedelta(seconds=min_delay - 1)
        assert clocked_time <= timezone.now() + timezone.timedelta(seconds=max_delay)
    else:
        # fallback is hardcode to 60
        assert clocked_time > timezone.now() + timezone.timedelta(seconds=_FALLBACK_DELAY_WITHOUT_CONFIG_SECONDS - 1)
        assert clocked_time <= timezone.now() + timezone.timedelta(seconds=_FALLBACK_DELAY_WITHOUT_CONFIG_SECONDS)
        assert f"Group strategy phase config not found for phase '{current_phase}'" in caplog.text
