import pytest
from unittest.mock import patch

from chat.services.summaries import _generate_top_10_summaries_for_school


@pytest.mark.parametrize(
    "response,expected",
    [
        (
            """["Teacher Alice reminds students about science fair project deadline.",
                "Teacher Bob discusses budget allocation for new lab equipment.",
                "Assistant moves budget discussion to next Monday's meeting.",
                "Principal Carol requests submission of quarterly reports by Friday.",
                "Teacher Alice asks John to finish grading lab reports by tomorrow.",
                "John confirms he'll finish grading lab reports by 5 PM.",
                "Teacher Bob praises Sara's science fair outline, requests hypothesis details.",
                "Sara thanks Teacher Bob and promises to add the details.",
                "Discussion on allocating budget for lab equipment is postponed.",
                "Science fair projects deadline reminder shared by Teacher Alice."]
        """,
            [
                "Teacher Alice reminds students about science fair project deadline.",
                "Teacher Bob discusses budget allocation for new lab equipment.",
                "Assistant moves budget discussion to next Monday's meeting.",
                "Principal Carol requests submission of quarterly reports by Friday.",
                "Teacher Alice asks John to finish grading lab reports by tomorrow.",
                "John confirms he'll finish grading lab reports by 5 PM.",
                "Teacher Bob praises Sara's science fair outline, requests hypothesis details.",
                "Sara thanks Teacher Bob and promises to add the details.",
                "Discussion on allocating budget for lab equipment is postponed.",
                "Science fair projects deadline reminder shared by Teacher Alice.",
            ],
        ),
        # non numbered
        (
            " ".join(
                [
                    "Teacher Alice reminds students about science fair project deadline.",
                    "Teacher Bob discusses budget allocation for new lab equipment.",
                    "Assistant moves budget discussion to next Monday's meeting.",
                    "Principal Carol requests submission of quarterly reports by Friday.",
                    "Teacher Alice asks John to finish grading lab reports by tomorrow.",
                    "John confirms he'll finish grading lab reports by 5 PM.",
                    "Teacher Bob praises Sara's science fair outline, requests hypothesis details.",
                    "Sara thanks Teacher Bob and promises to add the details.",
                    "Discussion on allocating budget for lab equipment is postponed.",
                    "Science fair projects deadline reminder shared by Teacher Alice.",
                ]
            ),
            [
                " ".join(
                    [
                        "Teacher Alice reminds students about science fair project deadline.",
                        "Teacher Bob discusses budget allocation for new lab equipment.",
                        "Assistant moves budget discussion to next Monday's meeting.",
                        "Principal Carol requests submission of quarterly reports by Friday.",
                        "Teacher Alice asks John to finish grading lab reports by tomorrow.",
                        "John confirms he'll finish grading lab reports by 5 PM.",
                        "Teacher Bob praises Sara's science fair outline, requests hypothesis details.",
                        "Sara thanks Teacher Bob and promises to add the details.",
                        "Discussion on allocating budget for lab equipment is postponed.",
                        "Science fair projects deadline reminder shared by Teacher Alice.",
                    ]
                )
            ],
        ),
    ],
)
@patch("chat.services.summaries.generate_response")
def test_generate_top_10_summaries_parsing(
    mock_generate_response,
    sunday_summary_prompt_factory,
    response,
    expected,
):
    # Prepare a dummy prompt in ControlConfig
    prompt = sunday_summary_prompt_factory(week=42, activity="test_value")
    # Stub out the LLM output - generate_response returns a tuple (response_text, prompt_tokens, completion_tokens)
    mock_generate_response.return_value = (response, 100, 50)

    summaries = _generate_top_10_summaries_for_school(
        all_individual_school_chats=[], all_group_school_chats=[], prompt=prompt
    )

    assert isinstance(summaries, list)
    assert summaries == expected


@patch("chat.services.summaries.generate_response")
def test_generate_top_10_summaries_integration_type_safety(mock_generate_response, sunday_summary_prompt_factory):
    """
    Test that the integration between generate_response and _parse_top_10_summaries
    works correctly with the actual return type of generate_response.
    This test specifically catches type mismatches like the one that caused the production error.
    """
    # Prepare a dummy prompt
    prompt = sunday_summary_prompt_factory(week=42, activity="test_value")
    
    # Mock generate_response to return the correct tuple format
    mock_generate_response.return_value = ("test response", 100, 50)
    
    # This should not raise any AttributeError about tuple not having strip method
    summaries = _generate_top_10_summaries_for_school(
        all_individual_school_chats=[], all_group_school_chats=[], prompt=prompt
    )
    
    # Verify the function completed successfully
    assert isinstance(summaries, list)
    # Since we mocked with "test response" (not JSON), it should return it as a single item
    assert summaries == ["test response"]
