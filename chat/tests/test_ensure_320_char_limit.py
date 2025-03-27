from unittest.mock import patch

# Import the function under test.
# Adjust the import path if your module is different.
from chat.completion import ensure_320_character_limit


# Case 1: When the input text is already under 320 characters,
# no call to chat_completion should be made and the text is returned unchanged.
def test_text_under_limit():
    short_text = "Short text"
    with patch("chat.completion.chat_completion") as mock_chat_completion:
        result = ensure_320_character_limit(short_text)
        assert result == short_text
        mock_chat_completion.assert_not_called()


# Case 2: When input is over 320 characters and chat_completion successfully shortens it
# (i.e. the shortened text returned is under 320 characters).
def test_successful_shortening():
    long_text = "A" * 400
    shortened_text = "B" * 300
    # On the first iteration, chat_completion returns a shortened text.
    with patch("chat.completion.chat_completion", return_value=shortened_text) as mock_chat_completion:
        result = ensure_320_character_limit(long_text)
        # After the first call, current_text becomes shortened_text (<320), so no further call.
        assert result == shortened_text
        mock_chat_completion.assert_called_once()


# Case 3: When input is over 320 and chat_completion does not shorten the text,
# and the text has no periods.
# After two iterations, the splitting logic kicks in and returns text[:320].
def test_unsuccessful_shortening_no_periods():
    long_text = "C" * 400
    # chat_completion returns the same text (no shortening).
    with patch("chat.completion.chat_completion", return_value=long_text) as mock_chat_completion:
        result = ensure_320_character_limit(long_text)
        # With no periods present, the splitting logic falls back to slicing the first 320 characters.
        assert result == long_text[:320]
        # Expect chat_completion to be called twice (once per iteration).
        assert mock_chat_completion.call_count == 2


# Case 4: When input is over 320, chat_completion is unsuccessful,
# but the text contains multiple sentences.
# The splitting logic should pop sentences until the joined text is under 320.
def test_unsuccessful_shortening_with_sentences():
    # Create three sentences; each sentence is 151 characters (150 letters + a period).
    sentence1 = "A" * 150 + "."
    sentence2 = "B" * 150 + "."
    sentence3 = "C" * 150 + "."
    # Combine sentences with spaces. Total length is >320.
    long_text = f"{sentence1} {sentence2} {sentence3}"
    # Simulate chat_completion being unsuccessful by returning the same text.
    with patch("chat.completion.chat_completion", return_value=long_text) as mock_chat_completion:
        result = ensure_320_character_limit(long_text)
        # re.split will split long_text into three sentences.
        # The while loop will pop the last sentence, leaving sentence1 and sentence2.
        expected = f"{sentence1} {sentence2}"
        assert result == expected
        assert mock_chat_completion.call_count == 2


# Case 5: When input is over 320 and has no valid sentences after splitting
# (e.g. a text consisting solely of spaces),
# the function should return the first 320 characters.
def test_unsuccessful_shortening_empty_sentences():
    # 330 spaces: no periods, and stripping produces an empty sentence list.
    long_text = " " * 330
    with patch("chat.completion.chat_completion", return_value=long_text) as mock_chat_completion:
        result = ensure_320_character_limit(long_text)
        # Since splitting yields no valid sentences, fallback to slicing.
        assert result == long_text[:320]
        assert mock_chat_completion.call_count == 2
