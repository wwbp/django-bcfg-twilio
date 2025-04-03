import pytest
from unittest.mock import patch

from chat.services.completion import MAX_RESPONSE_CHARACTER_LENGTH
from chat.services.individual_pipeline import individual_pipeline
from chat.models import (
    IndividualPipelineRecord,
    MessageType,
    IndividualPipelineStage,
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


@pytest.mark.django_db
@pytest.mark.parametrize(
    "description, participant_id, message, mocks, expected",
    [
        (
            "Standard Flow: Valid message, no moderation issues, non-test user.",
            "user_normal",
            "Test message",
            {
                "moderation_return": "",
                "get_moderation_message_return": None,
                "generate_response_return": "LLM response",
                "ensure_within_character_limit_return": "LLM response",
                "is_test_user": False,
            },
            {
                "expected_stages": [
                    IndividualPipelineStage.INGEST_PASSED,
                    IndividualPipelineStage.MODERATION_PASSED,
                    IndividualPipelineStage.PROCESS_PASSED,
                    IndividualPipelineStage.VALIDATE_PASSED,
                    IndividualPipelineStage.SEND_PASSED,
                ],
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
                "get_moderation_message_return": "Self-harm safety plan message",
                "generate_response_return": "LLM ignored",  # Not used
                "ensure_within_character_limit_return": "Self-harm safety plan message",
                "is_test_user": False,
            },
            {
                "expected_stages": [
                    IndividualPipelineStage.INGEST_PASSED,
                    IndividualPipelineStage.MODERATION_BLOCKED,
                    IndividualPipelineStage.VALIDATE_PASSED,
                    IndividualPipelineStage.SEND_PASSED,
                ],
                "expected_response": "Self-harm safety plan message",
                "expected_validated_message": "Self-harm safety plan message",
            },
        ),
        (
            "Long Response Flow: LLM returns a response over 320 characters; it is shortened before sending.",
            "user_long",
            "Message requiring long response shortening",
            {
                "moderation_return": "",
                "get_moderation_message_return": None,
                "generate_response_return": "L" * (MAX_RESPONSE_CHARACTER_LENGTH + 1),
                "ensure_within_character_limit_return": "Shortened response",
                "is_test_user": False,
            },
            {
                "expected_stages": [
                    IndividualPipelineStage.INGEST_PASSED,
                    IndividualPipelineStage.MODERATION_PASSED,
                    IndividualPipelineStage.PROCESS_PASSED,
                    IndividualPipelineStage.VALIDATE_CHARACTER_LIMIT_HIT,
                    IndividualPipelineStage.SEND_PASSED,
                ],
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
                "get_moderation_message_return": None,
                "generate_response_return": "LLM test response",
                "ensure_within_character_limit_return": "LLM test response",
                "is_test_user": True,
            },
            {
                "expected_stages": [
                    IndividualPipelineStage.INGEST_PASSED,
                    IndividualPipelineStage.MODERATION_PASSED,
                    IndividualPipelineStage.PROCESS_PASSED,
                    IndividualPipelineStage.VALIDATE_PASSED,
                ],
                "expected_response": "LLM test response",
                "expected_validated_message": "LLM test response",
            },
        ),
    ],
)
def test_individual_pipeline_parametrized(default_context, description, participant_id, message, mocks, expected):
    """
    Test the individual_pipeline task by simulating:
      - Message ingestion.
      - Moderation (with potential self-harm checks).
      - Prompt assembly, response generation, and response shortening if needed.
      - Sending the final response (or skipping for test users).
    """
    # Build the data with a uniform context from the fixture.
    data = {
        "message": message,
        "context": default_context,
    }
    with (
        patch(
            "chat.services.individual_pipeline.moderate_message", return_value=mocks["moderation_return"]
        ) as mock_mod,
        patch(
            "chat.services.individual_pipeline.get_moderation_message",
            return_value=mocks["get_moderation_message_return"] or "",
        ) as mock_get_mod,
        patch(
            "chat.services.individual_pipeline.generate_response", return_value=mocks["generate_response_return"]
        ) as mock_gen,
        patch(
            "chat.services.individual_pipeline.ensure_within_character_limit",
            return_value=mocks["ensure_within_character_limit_return"],
        ) as mock_ensure,
        patch(
            "chat.services.individual_pipeline.send_message_to_participant", return_value={"status": "ok"}
        ) as mock_send,
        patch("chat.services.individual_pipeline.is_test_user", return_value=mocks["is_test_user"]) as mock_is_test,
    ):
        individual_pipeline.run(participant_id, data)

    record = IndividualPipelineRecord.objects.get(participant_id=participant_id)

    # Assert that the stages recorded match exactly the expected list.
    assert record.stages == expected["expected_stages"], (
        f"{description}: Expected stages {expected['expected_stages']}, but got {record.stages}"
    )

    # Assert the response and validated_message fields.
    assert record.response == expected["expected_response"], (
        f"{description}: response expected {expected['expected_response']} but got {record.response}"
    )
    assert record.validated_message == expected["expected_validated_message"], (
        f"{description}: validated_message expected {expected['expected_validated_message']} but got {record.validated_message}"
    )

    # Assert generate_response call count:
    # Call count should be 0 if moderation returned a blocking value.
    expected_gen_calls = 0 if IndividualPipelineStage.MODERATION_BLOCKED in expected["expected_stages"] else 1
    assert mock_gen.call_count == expected_gen_calls, (
        f"{description}: generate_response call count expected {expected_gen_calls} but got {mock_gen.call_count}"
    )

    # Assert send_message_to_participant call count:
    # Should be 1 only if SEND_PASSED is in the expected stages.
    expected_send_calls = 1 if IndividualPipelineStage.SEND_PASSED in expected["expected_stages"] else 0
    assert mock_send.call_count == expected_send_calls, (
        f"{description}: send_message_to_participant call count expected {expected_send_calls} but got {mock_send.call_count}"
    )

    mock_is_test.assert_called_once_with(participant_id)
