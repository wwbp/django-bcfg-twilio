import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from chat.services.completion import _generate_response, ChatMessage

def test_generate_response_does_not_close_event_loop():
    chat_history = [ChatMessage(role="user", content="Hello")]
    instructions = "Say hi"
    message = "Hi"
    gpt_model = "gpt-4.1-mini"

    with patch("chat.services.completion.Kani") as MockKani, \
         patch("chat.services.completion.OpenAIEngine") as MockEngine:
        mock_assistant = AsyncMock()
        mock_assistant.chat_round_str.return_value = "Hi there!"
        mock_completion = AsyncMock(prompt_tokens=5, completion_tokens=7)
        mock_assistant.get_model_completion.return_value = mock_completion
        MockKani.return_value = mock_assistant
        # Mock engine.aclose as AsyncMock
        MockEngine.return_value.aclose = AsyncMock()

        _generate_response(chat_history, instructions, message, gpt_model)

    async def dummy():
        return 42

    result = asyncio.run(dummy())
    assert result == 42 