from unittest.mock import patch
from chat.services.completion import ensure_within_character_limit, MAX_RESPONSE_CHARACTER_LENGTH


# If text is already under the max, return it unchanged.
def test_text_under_limit():
    text = "Short text"
    with patch("chat.services.completion.chat_completion") as mock_chat_completion:
        result = ensure_within_character_limit(text)
        assert result == text
        mock_chat_completion.assert_not_called()


# Over max: chat_completion shortens the text to under MAX_RESPONSE_CHARACTER_LENGTH.
def test_successful_shortening():
    long_text = "A" * (MAX_RESPONSE_CHARACTER_LENGTH + 80)
    shortened_text = "B" * (MAX_RESPONSE_CHARACTER_LENGTH - 20)
    with patch("chat.services.completion.chat_completion", return_value=shortened_text) as mock_chat_completion:
        result = ensure_within_character_limit(long_text)
        assert result == shortened_text
        mock_chat_completion.assert_called_once()


# Over max with no periods: unsuccessful shortening triggers two chat_completion calls then a hard cutoff.
def test_unsuccessful_shortening_no_periods():
    long_text = "C" * (MAX_RESPONSE_CHARACTER_LENGTH + 80)
    with patch("chat.services.completion.chat_completion", return_value=long_text) as mock_chat_completion:
        result = ensure_within_character_limit(long_text)
        assert result == long_text[:MAX_RESPONSE_CHARACTER_LENGTH]
        assert mock_chat_completion.call_count == 2


# Over max with multiple sentences: if chat_completion fails, drop sentences until under max.
def test_unsuccessful_shortening_with_sentences():
    sentence_length = (MAX_RESPONSE_CHARACTER_LENGTH // 2) - 1
    s1 = "A" * (sentence_length - 1) + "."
    s2 = "B" * (sentence_length - 1) + "."
    s3 = "C" * (sentence_length - 1) + "."
    long_text = f"{s1} {s2} {s3}"
    with patch("chat.services.completion.chat_completion", return_value=long_text) as mock_chat_completion:
        result = ensure_within_character_limit(long_text)
        # Expect the last sentence dropped, leaving s1 and s2.
        expected = f"{s1} {s2}"
        assert result == expected
        assert mock_chat_completion.call_count == 2


# Over max with invalid sentences: if splitting yields no valid content, do a hard cutoff.
def test_unsuccessful_shortening_empty_sentences():
    long_text = "A1" * (MAX_RESPONSE_CHARACTER_LENGTH + 10)
    with patch("chat.services.completion.chat_completion", return_value=long_text) as mock_chat_completion:
        result = ensure_within_character_limit(long_text)
        assert result == long_text[:MAX_RESPONSE_CHARACTER_LENGTH]
        assert mock_chat_completion.call_count == 2
