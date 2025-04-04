import pytest
from unittest.mock import patch

from chat.services.completion import MAX_RESPONSE_CHARACTER_LENGTH
from chat.services.individual_pipeline import individual_pipeline_task
from chat.models import IndividualPipelineRecord, MessageType


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
                "expected_moderated": False,
                "expected_processed": True,
                "expected_sent": True,
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
                "generate_response_return": "LLM ignored",
                "ensure_within_character_limit_return": "Self-harm safety plan message",
                "is_test_user": False,
            },
            {
                "expected_moderated": True,
                "expected_processed": False,
                "expected_sent": True,
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
                "expected_moderated": False,
                "expected_processed": True,
                "expected_sent": True,
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
                "expected_moderated": False,
                "expected_processed": True,
                "expected_sent": False,
                "expected_response": "LLM test response",
                "expected_validated_message": "LLM test response",
            },
        ),
    ],
)
def test_individual_pipeline_parametrized(default_context, description, participant_id, message, mocks, expected):
    """
    Test the individual_pipeline_task for UC-AI-001 by simulating:
      - Message reception, queuing, and saving.
      - Moderation (including self-harm checks triggering a safety message).
      - Prompt assembly, response generation, and (if applicable) response shortening.
      - API call to the Hub to send the final response.
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
        individual_pipeline_task.run(participant_id, data)

    record = IndividualPipelineRecord.objects.get(participant_id=participant_id)

    # Asserts for record fields.
    for field, expected_field in [
        ("moderated", "expected_moderated"),
        ("processed", "expected_processed"),
        ("sent", "expected_sent"),
        ("response", "expected_response"),
        ("validated_message", "expected_validated_message"),
    ]:
        actual = getattr(record, field)
        exp_value = expected[expected_field]
        assert actual == exp_value, f"{description}: {field} expected {exp_value} but got {actual}"

    # Assert generate_response call count.
    expected_gen_calls = 0 if expected["expected_moderated"] else 1
    assert mock_gen.call_count == expected_gen_calls, (
        f"{description}: generate_response call count expected {expected_gen_calls} but got {mock_gen.call_count}"
    )

    # Assert send_message_to_participant call count.
    expected_send_calls = (
        0 if mocks["is_test_user"] or not (expected["expected_processed"] or expected["expected_moderated"]) else 1
    )
    assert mock_send.call_count == expected_send_calls, (
        f"{description}: send_message_to_participant call count expected {expected_send_calls} but "
        f"got {mock_send.call_count}"
    )

    mock_is_test.assert_called_once_with(participant_id)
