import copy
from uuid import UUID, uuid4

import pytest

from chat.models import ControlConfig, IndividualChatTranscript, IndividualPipelineRecord, MessageType, IndividualPrompt
from chat.serializers import IndividualIncomingMessageSerializer
from chat.services.individual_pipeline import individual_ingest, individual_pipeline
from chat.tests.conftest import IndividualPipelineMocks


_INITIAL_MESSAGE = "Some initial message"
# we make this really long so that it invokes the character limitation process
_GENERATED_LLM_RESPONSE = (
    "Some LLM response Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod "
    "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud "
    "exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor "
    "in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur."
)
_SHORTENED_LLM_RESPONSE = "Some shortened LLM response"
_FIRST_USER_MESSAGE = "some message from user"


@pytest.fixture
def inbound_call_and_mocks(
    mock_all_individual_external_calls, control_config_factory
) -> tuple[UUID, dict, IndividualPipelineMocks]:
    participant_id = uuid4()
    inbound_payload = {
        "message": _FIRST_USER_MESSAGE,
        "context": {
            "school_name": "Test School",
            "school_mascot": "Default Mascot",
            "initial_message": _INITIAL_MESSAGE,
            "week_number": 1,
            "name": "Default Name",
            "message_type": MessageType.INITIAL,
        },
    }

    IndividualPrompt.objects.create(
        week=inbound_payload["context"]["week_number"],  # type: ignore[index]
        message_type=inbound_payload["context"]["message_type"],  # type: ignore[index]
        activity="base activity",
    )
    control_config_factory(key=ControlConfig.ControlConfigKey.PERSONA_PROMPT, value="test persona prompt")
    control_config_factory(key=ControlConfig.ControlConfigKey.SYSTEM_PROMPT, value="test system prompt")
    control_config_factory(
        key=ControlConfig.ControlConfigKey.INSTRUCTION_PROMPT_TEMPLATE,
        value="INSTRUCTION_PROMPT_TEMPLATE",
    )

    mock_all_individual_external_calls.mock_generate_response.return_value = _GENERATED_LLM_RESPONSE
    mock_all_individual_external_calls.mock_ensure_within_character_limit.return_value = _SHORTENED_LLM_RESPONSE

    return participant_id, inbound_payload, mock_all_individual_external_calls


def test_individual_process_does_not_skip_if_one_message(inbound_call_and_mocks):
    participant_id, inbound_payload, mock_all_individual_external_calls = inbound_call_and_mocks
    mock_all_individual_external_calls.mock_generate_response.return_value = _GENERATED_LLM_RESPONSE
    mock_all_individual_external_calls.mock_ensure_within_character_limit.return_value = _SHORTENED_LLM_RESPONSE

    individual_pipeline.run(participant_id, inbound_payload)

    records = list(IndividualPipelineRecord.objects.all())
    assert len(records) == 1
    assert records[0].user.id == str(participant_id)
    assert records[0].status == IndividualPipelineRecord.StageStatus.SEND_PASSED
    transcripts = list(IndividualChatTranscript.objects.order_by("created_at").all())
    assert len(transcripts) == 3
    assert transcripts[0].content == _INITIAL_MESSAGE
    assert transcripts[1].content == _FIRST_USER_MESSAGE
    assert transcripts[2].content == _SHORTENED_LLM_RESPONSE


def test_individual_process_skips_if_message_arrives_during_moderation(inbound_call_and_mocks):
    participant_id, inbound_payload, mock_all_individual_external_calls = inbound_call_and_mocks
    _second_payload = copy.deepcopy(inbound_payload)
    _second_payload["message"] = "some message from user during first moderation"

    serializer = IndividualIncomingMessageSerializer(data=_second_payload)
    serializer.is_valid(raise_exception=True)
    second_payload = serializer.validated_data

    def mock_moderate_message(*args, **kwargs):
        # mock another message is ingested here
        individual_ingest(participant_id, second_payload)
        return ""

    mock_all_individual_external_calls.mock_moderate_message.side_effect = mock_moderate_message

    individual_pipeline.run(participant_id, inbound_payload)

    records = list(IndividualPipelineRecord.objects.order_by("created_at").all())
    assert len(records) == 2
    assert all(record.user.id == str(participant_id) for record in records)
    assert records[0].status == IndividualPipelineRecord.StageStatus.PROCESS_SKIPPED
    assert records[1].status == IndividualPipelineRecord.StageStatus.INGEST_PASSED
    transcripts = list(IndividualChatTranscript.objects.order_by("created_at").all())
    assert len(transcripts) == 3
    assert transcripts[0].content == _INITIAL_MESSAGE
    assert transcripts[1].content == _FIRST_USER_MESSAGE
    assert transcripts[2].content == "some message from user during first moderation"
    # when second message is processed, we'd record LLM response here


def test_individual_process_skips_if_message_arrives_during_generate(inbound_call_and_mocks):
    participant_id, inbound_payload, mock_all_individual_external_calls = inbound_call_and_mocks
    _second_payload = copy.deepcopy(inbound_payload)
    _second_payload["message"] = "some message from user during first generation"

    serializer = IndividualIncomingMessageSerializer(data=_second_payload)
    serializer.is_valid(raise_exception=True)
    second_payload = serializer.validated_data

    def mock_generate_response(*args, **kwargs):
        # mock another message is ingested here
        individual_ingest(participant_id, second_payload)
        return _GENERATED_LLM_RESPONSE

    mock_all_individual_external_calls.mock_generate_response.side_effect = mock_generate_response

    individual_pipeline.run(participant_id, inbound_payload)

    records = list(IndividualPipelineRecord.objects.order_by("created_at").all())
    assert len(records) == 2
    assert all(record.user.id == str(participant_id) for record in records)
    assert records[0].status == IndividualPipelineRecord.StageStatus.PROCESS_SKIPPED
    assert records[1].status == IndividualPipelineRecord.StageStatus.INGEST_PASSED
    transcripts = list(IndividualChatTranscript.objects.order_by("created_at").all())
    assert len(transcripts) == 3
    assert transcripts[0].content == _INITIAL_MESSAGE
    assert transcripts[1].content == _FIRST_USER_MESSAGE
    assert transcripts[2].content == "some message from user during first generation"
    # when second message is processed, we'd record LLM response here


def test_individual_process_skips_if_message_arrives_during_validate(inbound_call_and_mocks):
    participant_id, inbound_payload, mock_all_individual_external_calls = inbound_call_and_mocks
    _second_payload = copy.deepcopy(inbound_payload)
    _second_payload["message"] = "some message from user during first validation"

    serializer = IndividualIncomingMessageSerializer(data=_second_payload)
    serializer.is_valid(raise_exception=True)
    second_payload = serializer.validated_data

    def mock_ensure_within_character_limit(*args, **kwargs):
        # mock another message is ingested here
        individual_ingest(participant_id, second_payload)
        return _GENERATED_LLM_RESPONSE

    mock_all_individual_external_calls.mock_ensure_within_character_limit.side_effect = (
        mock_ensure_within_character_limit
    )

    individual_pipeline.run(participant_id, inbound_payload)

    records = list(IndividualPipelineRecord.objects.order_by("created_at").all())
    assert len(records) == 2
    assert all(record.user.id == str(participant_id) for record in records)
    assert records[0].status == IndividualPipelineRecord.StageStatus.PROCESS_SKIPPED
    assert records[1].status == IndividualPipelineRecord.StageStatus.INGEST_PASSED
    transcripts = list(IndividualChatTranscript.objects.order_by("created_at").all())
    assert len(transcripts) == 3
    assert transcripts[0].content == _INITIAL_MESSAGE
    assert transcripts[1].content == _FIRST_USER_MESSAGE
    assert transcripts[2].content == "some message from user during first validation"
    # when second message is processed, we'd record LLM response here
