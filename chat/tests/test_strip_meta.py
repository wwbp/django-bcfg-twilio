from chat.services.individual_crud import strip_meta


# 1. Single-line leading metadata
def test_strip_meta_single_line():
    raw = "[meta]: Hello, world!"
    assert strip_meta(raw) == "Hello, world!"


# 2. Multi-line with metadata only on first line
def test_strip_meta_first_line_only():
    raw = "[info]: First line\nSecond line\nThird line"
    expected = "First line\nSecond line\nThird line"
    assert strip_meta(raw) == expected


# 3. Multiple metadata tags on different lines
def test_strip_meta_multiple_lines():
    raw = "[a]: One\n[b]: Two\nNo tag here"
    expected = "One\nTwo\nNo tag here"
    assert strip_meta(raw) == expected


# 4. No metadata at all
def test_strip_meta_no_metadata():
    raw = "Just some text\nAnother line"
    assert strip_meta(raw) == raw


# 5. Metadata-like pattern mid-line shouldn’t be removed
def test_strip_meta_inline_pattern():
    raw = "A sentence with [skip]: this inside."
    assert strip_meta(raw) == raw


# 6. Empty string
def test_strip_meta_empty():
    assert strip_meta("") == ""


# 7. Metadata with extra spaces
def test_strip_meta_spaces():
    raw = "[tag]:    Content starts with spaces"
    assert strip_meta(raw) == "Content starts with spaces"


def test_strip_meta_assistant_name_colon_suffix():
    raw = "bot: Hello there"
    assert strip_meta(raw, "bot") == "Hello there"


def test_strip_meta_assistant_name_colon_prefix():
    raw = ": bot Hello there"
    assert strip_meta(raw, "bot") == "Hello there"


def test_strip_meta_assistant_name_both_colons():
    raw = ": bot : Hello there"
    assert strip_meta(raw, "bot") == "Hello there"


def test_strip_meta_no_colon():
    raw = "[meta]No colon"
    assert strip_meta(raw) == "No colon"


def test_strip_meta_no_colon_with_space():
    raw = "[meta] Content after"
    assert strip_meta(raw) == "Content after"


def test_strip_meta_inline_pattern_no_colon():
    raw = "A sentence with [skip] this inside."
    assert strip_meta(raw) == raw
