import pytest
from unittest.mock import patch

from chat.services.completion import _generate_response, generate_response


# Parameterized test for _generate_response
@pytest.mark.parametrize(
    "chat_history, instructions, message, expected_response",
    [
        ([], "Test instructions", "Test message", "mocked response"),
        ([{"role": "user", "content": "Hello"}], "Other instructions", "Another message", "mocked response"),
    ],
)
@patch("chat.services.completion.Kani")
@patch("chat.services.completion.OpenAIEngine")
def test__generate_response_param(mock_openai, mock_kani, chat_history, instructions, message, expected_response):
    # Define a dummy async function to simulate assistant.chat_round_str.
    async def dummy_chat_round_str(msg):
        return expected_response

    # Configure the mocked Kani instance.
    mock_kani.return_value.chat_round_str.side_effect = dummy_chat_round_str

    async def dummy_get_model_completion():
        class Dummy:
            prompt_tokens = None
            completion_tokens = None

        return Dummy()

    mock_kani.return_value.get_model_completion.side_effect = dummy_get_model_completion

    result, _, _ = _generate_response(chat_history, instructions, message, "gpt-4o-mini")
    assert result == expected_response
    mock_kani.return_value.chat_round_str.assert_called_once_with(message)


# Parameterized test for generate_response
@pytest.mark.parametrize(
    "history_json, expected_call_count, expected_result",
    [
        ([{"content": "Hello"}, {"content": "World"}], 2, "mocked response"),
        ([{"content": "Only one"}], 1, "mocked response"),
        ([], 0, "mocked response"),
    ],
)
@patch("chat.services.completion._generate_response", return_value=("mocked response", None, None))
@patch("chat.services.completion.ChatMessage")
def test_generate_response_param(
    mock_chatmessage, mock_generate_response, history_json, expected_call_count, expected_result
):
    # Dummy model_validate simply returns the 'content' value.
    def dummy_model_validate(data):
        return data["content"]

    mock_chatmessage.model_validate.side_effect = dummy_model_validate

    result, _, _ = generate_response(history_json, "Test instructions", "Test message", "gpt-4o-mini")
    # Verify model_validate was called once for each dict in history_json.
    assert mock_chatmessage.model_validate.call_count == expected_call_count
    assert result == expected_result
