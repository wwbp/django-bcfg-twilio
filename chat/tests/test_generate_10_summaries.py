import pytest
from unittest.mock import patch

from chat.services.summaries import _generate_top_10_summaries_for_school


@pytest.mark.parametrize(
    "response,expected",
    [
        (
            """["Teacher Alice reminds students about science fair project deadline.",
                "Teacher Bob discusses budget allocation for new lab equipment.",
                "Assistant moves budget discussion to next Monday’s meeting.",
                "Principal Carol requests submission of quarterly reports by Friday.",
                "Teacher Alice asks John to finish grading lab reports by tomorrow.",
                "John confirms he’ll finish grading lab reports by 5 PM.",
                "Teacher Bob praises Sara’s science fair outline, requests hypothesis details.",
                "Sara thanks Teacher Bob and promises to add the details.",
                "Discussion on allocating budget for lab equipment is postponed.",
                "Science fair projects deadline reminder shared by Teacher Alice."]
        """,
            [
                "Teacher Alice reminds students about science fair project deadline.",
                "Teacher Bob discusses budget allocation for new lab equipment.",
                "Assistant moves budget discussion to next Monday’s meeting.",
                "Principal Carol requests submission of quarterly reports by Friday.",
                "Teacher Alice asks John to finish grading lab reports by tomorrow.",
                "John confirms he’ll finish grading lab reports by 5 PM.",
                "Teacher Bob praises Sara’s science fair outline, requests hypothesis details.",
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
                    "Assistant moves budget discussion to next Monday’s meeting.",
                    "Principal Carol requests submission of quarterly reports by Friday.",
                    "Teacher Alice asks John to finish grading lab reports by tomorrow.",
                    "John confirms he’ll finish grading lab reports by 5 PM.",
                    "Teacher Bob praises Sara’s science fair outline, requests hypothesis details.",
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
                        "Assistant moves budget discussion to next Monday’s meeting.",
                        "Principal Carol requests submission of quarterly reports by Friday.",
                        "Teacher Alice asks John to finish grading lab reports by tomorrow.",
                        "John confirms he’ll finish grading lab reports by 5 PM.",
                        "Teacher Bob praises Sara’s science fair outline, requests hypothesis details.",
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
    sunday_summary_prompt_factory(week=42, activity="test_value")
    # Stub out the LLM output
    mock_generate_response.return_value = response

    summaries = _generate_top_10_summaries_for_school(
        school_name="TestSchool",
        school_week_number=42,
        all_individual_school_chats=[],
        all_group_school_chats=[],
    )

    assert isinstance(summaries, list)
    assert summaries == expected
