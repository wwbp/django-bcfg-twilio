import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from chat.services.completion import _generate_response, generate_response, ChatMessage


# Parameterized test for _generate_response
@pytest.mark.parametrize(
    "chat_history,instructions,message,expected_response",
    [
        ([{"role": "user", "content": "Hi"}], "Test instructions", "Test message", "mocked response"),
        ([{"role": "user", "content": "Hello"}], "Other instructions", "Another message", "mocked response"),
    ],
)
@patch("chat.services.completion.Kani")
@patch("chat.services.completion.OpenAIEngine")
def test__generate_response_param(mock_engine, mock_kani, chat_history, instructions, message, expected_response):
    # Setup AsyncMock for assistant
    mock_assistant = AsyncMock()
    mock_assistant.chat_round_str.return_value = expected_response
    mock_completion = MagicMock(prompt_tokens=5, completion_tokens=7)
    mock_assistant.get_model_completion.return_value = mock_completion
    mock_kani.return_value = mock_assistant

    # Mock engine.aclose as AsyncMock
    mock_engine.return_value.aclose = AsyncMock()

    # Convert chat_history dicts to ChatMessage objects
    chat_history_objs = [ChatMessage.model_validate(chat) for chat in chat_history]
    response, prompt_tokens, completion_tokens = _generate_response(chat_history_objs, instructions, message, "gpt-4.1-mini")
    assert response == expected_response
    assert prompt_tokens == 5
    assert completion_tokens == 7


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
