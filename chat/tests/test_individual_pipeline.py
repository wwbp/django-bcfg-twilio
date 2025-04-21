from unittest.mock import patch
from uuid import uuid4
import pytest

from chat.services.completion import MAX_RESPONSE_CHARACTER_LENGTH
from chat.services.individual_pipeline import individual_pipeline
from chat.models import (
    BaseChatTranscript,
    ControlConfig,
    IndividualChatTranscript,
    IndividualPipelineRecord,
    MessageType,
    IndividualPrompt,
    User,
)


# Define a fixture for the default context that does not affect the test.
@pytest.fixture
def default_context():
    return {
        "school_name": "Test School",
        "school_mascot": "Default Mascot",
        "initial_message": "Hello",
        "week_number": 1,
        "name": "Default Name",
        "message_type": MessageType.INITIAL,
    }


@pytest.mark.parametrize(
    "description, participant_id, message, mocks, expected",
    [
        (
            "Standard Flow: Valid message, no moderation issues, non-test user.",
            "user_normal",
            "Test message",
            {
                "moderation_return": "",
                "generate_response_return": "LLM response",
                "ensure_within_character_limit_return": "LLM response",
                "is_test_user": False,
            },
            {
                "expected_status": IndividualPipelineRecord.StageStatus.SEND_PASSED,
                "expected_response": "LLM response",
                "expected_validated_message": "LLM response",
            },
        ),
        (
            "Safety Plan Flow: Message flagged as self-harm; processing halted and safety message is sent.",
            "user_safety",
            "Message with self-harm content",
            {
                "moderation_return": "self-harm",
                "generate_response_return": "LLM ignored",  # Not used
                "ensure_within_character_limit_return": "Self-harm safety plan message",
                "is_test_user": False,
            },
            {
                "expected_status": IndividualPipelineRecord.StageStatus.MODERATION_BLOCKED,
                "expected_response": None,
                "expected_validated_message": None,
            },
        ),
        (
            "Long Response Flow: LLM returns a response over 320 characters; it is shortened before sending.",
            "user_long",
            "Message requiring long response shortening",
            {
                "moderation_return": "",
                "generate_response_return": "L" * (MAX_RESPONSE_CHARACTER_LENGTH + 1),
                "ensure_within_character_limit_return": "Shortened response",
                "is_test_user": False,
            },
            {
                "expected_status": IndividualPipelineRecord.StageStatus.SEND_PASSED,
                "expected_response": "L" * (MAX_RESPONSE_CHARACTER_LENGTH + 1),
                "expected_validated_message": "Shortened response",
            },
        ),
        (
            "Test User Flow: Processed normally but sending is skipped for test users.",
            "user_test",
            "Test message for test user",
            {
                "moderation_return": "",
                "generate_response_return": "LLM test response",
                "ensure_within_character_limit_return": "LLM test response",
                "is_test_user": True,
            },
            {
                "expected_status": IndividualPipelineRecord.StageStatus.VALIDATE_PASSED,
                "expected_response": "LLM test response",
                "expected_validated_message": "LLM test response",
            },
        ),
    ],
)
def test_individual_pipeline_parametrized(
    default_context,
    description,
    participant_id,
    message,
    mocks,
    expected,
    mock_all_individual_external_calls,
    caplog,
    control_config_factory,
):
    """
    Test the individual_pipeline task by simulating:
      - Message ingestion.
      - Moderation.
      - Prompt assembly, response generation, and response shortening if needed.
      - Sending the final response (or skipping for test users).
    """
    # Build the data with a uniform context from the fixture.
    data = {
        "message": message,
        "context": default_context,
    }
    IndividualPrompt.objects.create(
        week=default_context["week_number"],
        message_type=default_context["message_type"],
        activity="base activity",
    )
    control_config_factory(key=ControlConfig.ControlConfigKey.PERSONA_PROMPT, value="test persona prompt")
    control_config_factory(key=ControlConfig.ControlConfigKey.SYSTEM_PROMPT, value="test system prompt")
    user = User.objects.create(id=participant_id, is_test=mocks["is_test_user"])
    mock_all_individual_external_calls.mock_moderate_message.return_value = mocks["moderation_return"]
    mock_all_individual_external_calls.mock_generate_response.return_value = mocks["generate_response_return"]
    mock_all_individual_external_calls.mock_ensure_within_character_limit.return_value = mocks[
        "ensure_within_character_limit_return"
    ]
    individual_pipeline.run(participant_id, data)

    record = IndividualPipelineRecord.objects.get(user=user)

    # Assert that the final status recorded matches the expected status.
    assert record.status == expected["expected_status"], (
        f"{description}: Expected status {expected['expected_status']}, but got {record.status}"
    )

    # Assert the response and validated_message fields.
    assert record.response == expected["expected_response"], (
        f"{description}: response expected {expected['expected_response']} but got {record.response}"
    )
    assert record.validated_message == expected["expected_validated_message"], (
        f"{description}: validated_message expected {expected['expected_validated_message']} "
        f"but got {record.validated_message}"
    )

    # Assert generate_response call count:
    # Call count should be 0 if moderation returned a blocking value.
    expected_gen_calls = 0 if mocks["moderation_return"] else 1
    assert mock_all_individual_external_calls.mock_generate_response.call_count == expected_gen_calls, (
        f"{description}: generate_response call count expected {expected_gen_calls} but got "
        f"{mock_all_individual_external_calls.mock_generate_response.call_count}"
    )

    # Asser moderation message send
    # Call count should be 1 if moderation returned a blocking value.
    expected_send_moderation_calls = 1 if mocks["moderation_return"] else 0
    assert (
        mock_all_individual_external_calls.mock_send_moderation_message.call_count == expected_send_moderation_calls
    ), (
        f"{description}: send_moderation_message call count expected {expected_send_moderation_calls} "
        f"but got {mock_all_individual_external_calls.mock_send_moderation_message.call_count}"
    )

    # Assert send_message_to_participant call count:
    # Should be 1 if not a test user and message not moderated.
    expected_send_calls = 1 if not (mocks["is_test_user"] or mocks["moderation_return"]) else 0
    assert mock_all_individual_external_calls.mock_send_message_to_participant.call_count == expected_send_calls, (
        f"{description}: send_message_to_participant call count expected {expected_send_calls} "
        f"but got {mock_all_individual_external_calls.mock_send_message_to_participant.call_count}"
    )

    user_chat_transcript = (
        record.user.current_session.transcripts.filter(role=BaseChatTranscript.Role.USER)
        .order_by("-created_at")
        .first()
    )
    if expected["expected_status"] == IndividualPipelineRecord.StageStatus.MODERATION_BLOCKED:
        assert user_chat_transcript.moderation_status == IndividualChatTranscript.ModerationStatus.FLAGGED
        assert record.user.current_session.transcripts.count() == 2  # initial and user, no assistant
    else:
        assert user_chat_transcript.moderation_status == IndividualChatTranscript.ModerationStatus.NOT_FLAGGED
        assert record.user.current_session.transcripts.count() == 3  # initial, user, assistant response

    # confirm this was not for direct messaging
    assert "direct-messaging" not in caplog.text
    assert IndividualPipelineRecord.objects.filter(is_for_group_direct_messaging=True).count() == 0


@patch("chat.services.individual_pipeline.individual_ingest")
def test_individual_pipeline_handles_exception_before_ingestion(mock_individual_ingest, caplog):
    participant_id = uuid4()
    inbound_payload = {
        "message": "Some user message",
        "context": {
            "school_name": "Test School",
            "school_mascot": "Default Mascot",
            "initial_message": "Some initial message",
            "week_number": 1,
            "name": "Default Name",
            "message_type": MessageType.INITIAL,
        },
    }
    mock_individual_ingest.side_effect = Exception("Simulated exception")
    with pytest.raises(Exception) as e:
        individual_pipeline.run(participant_id, inbound_payload)
    assert f"Individual pipeline failed for participant {participant_id}" in caplog.text
    assert "Simulated exception" in caplog.text
    assert IndividualPipelineRecord.objects.count() == 0


@patch("chat.services.individual_pipeline.individual_moderation")
def test_individual_pipeline_handles_exception_after_ingestion(mock_individual_moderation, caplog):
    participant_id = uuid4()
    inbound_payload = {
        "message": "Some user message",
        "context": {
            "school_name": "Test School",
            "school_mascot": "Default Mascot",
            "initial_message": "Some initial message",
            "week_number": 1,
            "name": "Default Name",
            "message_type": MessageType.INITIAL,
        },
    }
    mock_individual_moderation.side_effect = Exception("Simulated exception")
    with pytest.raises(Exception) as e:
        individual_pipeline.run(participant_id, inbound_payload)
    assert f"Individual pipeline failed for participant {participant_id}" in caplog.text
    assert "Simulated exception" in caplog.text
    assert IndividualPipelineRecord.objects.count() == 1
    assert IndividualPipelineRecord.objects.first().status == IndividualPipelineRecord.StageStatus.FAILED
