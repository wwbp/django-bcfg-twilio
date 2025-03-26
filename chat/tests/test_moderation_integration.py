from unittest.mock import MagicMock, patch
from chat.moderation import moderate_message
import pytest


@patch("chat.moderation.OpenAI")
@patch("chat.moderation.model_dump")
@pytest.mark.parametrize("self_harm_score,should_flag", [[0.1, False], [0.9, True]])
def test_self_harm_triggered(model_dump_mock, open_ai_mock, self_harm_score, should_flag):
    moderation_response = MagicMock()
    moderation_response.results[0].category_scores = {}
    open_ai_mock.return_value.moderations.create.return_value = moderation_response
    model_dump_mock.return_value = {
        "self-harm": self_harm_score,
    }
    test_message = "I feel so lost and I want to hurt myself."
    result = moderate_message(test_message)
    print("Test self-harm triggered result:", result)
    if should_flag:
        assert "self-harm" in result
    else:
        assert result == ""
