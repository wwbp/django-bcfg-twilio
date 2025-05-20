import datetime
from unittest.mock import MagicMock, patch
from django.test import override_settings
from freezegun import freeze_time
from django.utils import timezone
from chat.models import (
    BaseChatTranscript,
    MessageType,
    Summary,
)
from django.contrib.auth.models import Group as AuthGroup, User as AuthUser
from admin.models import AuthGroupName
from chat.services.summaries import generate_weekly_summaries, notify_on_missing_summaries


# Helper class to simulate httpx.Client as a context manager.
class FakeClientContextManager:
    def __init__(self, client):
        self.client = client

    def __enter__(self):
        return self.client

    def __exit__(self, exc_type, exc_value, traceback):
        pass


def get_client_patch(mock_client):
    return FakeClientContextManager(mock_client)


@freeze_time("2025-04-17T20:00:00")
@patch("chat.services.summaries._generate_top_10_summaries_for_school")
def test_generate_weekly_summaries(
    mock_generate_top_10_summaries_for_school,
    group_factory,
    user_factory,
    individual_session_factory,
    group_session_factory,
    individual_chat_transcript_factory,
    group_chat_transcript_factory,
    sunday_summary_prompt_factory,
    caplog,
):
    mock_generate_top_10_summaries_for_school.return_value = ["Summary 1", "Summary 2"]
    school1 = "Group and Indiv School"
    school2 = "Indiv Only School"
    school3 = "Group Only School"
    school4 = "Test School"
    school5 = "Old School"
    school6 = "No Prompt School"
    transcript_date = timezone.make_aware(datetime.datetime(2025, 4, 15, 15, 0))
    old_transcript_date = timezone.make_aware(datetime.datetime(2025, 4, 8, 15, 0))
    sunday_summary_prompt_factory(week=5, activity="test_value")

    # School 1 setup - both group and individual chats
    school1_group1 = group_factory()
    school1_group1_user1 = user_factory(group=school1_group1, school_name=school1)
    school1_group1_user2 = user_factory(group=school1_group1, school_name=school1)
    school1_group2 = group_factory()
    school1_group2_user1 = user_factory(group=school1_group2, school_name=school1)
    school1_indiv_user1 = user_factory(school_name=school1)
    school1_indiv_user2 = user_factory(school_name=school1)
    school1_group_session1 = group_session_factory(
        group=school1_group1,
        week_number=5,
        message_type=MessageType.INITIAL,
    )
    school1_group_session2 = group_session_factory(
        group=school1_group1,
        week_number=5,
        message_type=MessageType.REMINDER,
    )
    school1_group_session3 = group_session_factory(
        group=school1_group2,
        week_number=5,
        message_type=MessageType.INITIAL,
    )
    school1_group_session4 = group_session_factory(
        group=school1_group2,
        week_number=4,  # old week number
        message_type=MessageType.INITIAL,
    )
    school1_indiv_session1 = individual_session_factory(
        user=school1_indiv_user1,
        week_number=5,
        message_type=MessageType.INITIAL,
    )
    school1_indiv_session2 = individual_session_factory(
        user=school1_indiv_user1,
        week_number=5,
        message_type=MessageType.SUMMARY,
    )
    school1_indiv_session3 = individual_session_factory(
        user=school1_indiv_user2,
        week_number=5,
        message_type=MessageType.INITIAL,
    )
    school1_indiv_session4 = individual_session_factory(
        user=school1_indiv_user2,
        week_number=4,  # old week number
        message_type=MessageType.INITIAL,
    )
    school1_included_group_chats = []
    school1_included_group_chats.extend(
        group_chat_transcript_factory.create_batch(
            10,
            session=school1_group_session1,
            sender=school1_group1_user1,
            role=BaseChatTranscript.Role.USER,
            created_at=transcript_date,
        )
    )
    school1_included_group_chats.extend(
        group_chat_transcript_factory.create_batch(
            10,
            session=school1_group_session2,
            sender=school1_group1_user2,
            role=BaseChatTranscript.Role.USER,
            created_at=transcript_date,
        )
    )
    school1_included_group_chats.extend(
        group_chat_transcript_factory.create_batch(
            10,
            session=school1_group_session3,
            sender=school1_group2_user1,
            role=BaseChatTranscript.Role.USER,
            created_at=transcript_date,
        )
    )
    # these chats not included as they are from the previous week
    group_chat_transcript_factory.create_batch(
        10,
        session=school1_group_session4,
        sender=school1_group2_user1,
        role=BaseChatTranscript.Role.USER,
        created_at=old_transcript_date,
    )
    school1_included_individual_chats = []
    school1_included_individual_chats.extend(
        individual_chat_transcript_factory.create_batch(
            10,
            session=school1_indiv_session1,
            role=BaseChatTranscript.Role.USER,
            created_at=transcript_date,
        )
    )
    school1_included_individual_chats.extend(
        individual_chat_transcript_factory.create_batch(
            10,
            session=school1_indiv_session2,
            role=BaseChatTranscript.Role.USER,
            created_at=transcript_date,
        )
    )
    school1_included_individual_chats.extend(
        individual_chat_transcript_factory.create_batch(
            10,
            session=school1_indiv_session3,
            role=BaseChatTranscript.Role.USER,
            created_at=transcript_date,
        )
    )
    # these chats not included as they are from the previous week
    individual_chat_transcript_factory.create_batch(
        10,
        session=school1_indiv_session4,
        role=BaseChatTranscript.Role.USER,
        created_at=old_transcript_date,
    )

    # School 2 setup - only has individual chats
    school2_indiv_user1 = user_factory(school_name=school2)
    school2_indiv_session = individual_session_factory(
        user=school2_indiv_user1,
        week_number=5,
        message_type=MessageType.INITIAL,
    )
    individual_chat_transcript_factory(
        session=school2_indiv_session,
        role=BaseChatTranscript.Role.USER,
        content="Individual message 1",
        created_at=transcript_date,
    )

    # School 3 setup - only has group chats
    school3_group1 = group_factory()
    school3_group1_user1 = user_factory(group=school3_group1, school_name=school3)
    school3_group_session = group_session_factory(
        group=school3_group1,
        week_number=5,
        message_type=MessageType.INITIAL,
    )
    group_chat_transcript_factory(
        session=school3_group_session,
        sender=school3_group1_user1,
        role=BaseChatTranscript.Role.USER,
        content="Group message 1",
        created_at=transcript_date,
    )

    # School 4 - Has only test users and groups
    school4_group1 = group_factory(is_test=True)
    school4_group1_user1 = user_factory(group=school4_group1, school_name=school4, is_test=True)
    school4_indiv_user1 = user_factory(school_name=school4, is_test=True)
    school4_group_session = group_session_factory(
        group=school4_group1,
        week_number=5,
        message_type=MessageType.INITIAL,
    )
    school4_indiv_session = individual_session_factory(
        user=school4_indiv_user1,
        week_number=5,
        message_type=MessageType.INITIAL,
    )
    group_chat_transcript_factory(
        session=school4_group_session,
        sender=school4_group1_user1,
        role=BaseChatTranscript.Role.USER,
        content="Group message 1",
        created_at=transcript_date,
    )
    individual_chat_transcript_factory(
        session=school4_indiv_session,
        role=BaseChatTranscript.Role.USER,
        content="Individual message 1",
        created_at=transcript_date,
    )

    # School 5 - Has only old transcripts
    school5_group1 = group_factory()
    school5_group1_user1 = user_factory(group=school5_group1, school_name=school5)
    school5_indiv_user1 = user_factory(school_name=school5)
    school5_group_session = group_session_factory(
        group=school5_group1,
        week_number=5,
        message_type=MessageType.INITIAL,
    )
    school5_indiv_session = individual_session_factory(
        user=school5_indiv_user1,
        week_number=5,
        message_type=MessageType.INITIAL,
    )
    group_chat_transcript_factory(
        session=school5_group_session,
        sender=school5_group1_user1,
        role=BaseChatTranscript.Role.USER,
        content="Group message 1",
        created_at=transcript_date - datetime.timedelta(weeks=1),
    )
    individual_chat_transcript_factory(
        session=school5_indiv_session,
        role=BaseChatTranscript.Role.USER,
        content="Individual message 1",
        created_at=transcript_date - datetime.timedelta(weeks=1),
    )

    # School 6 - No prompt for the week
    school6_group1 = group_factory()
    school6_group1_user1 = user_factory(group=school6_group1, school_name=school6)
    school6_group_session = group_session_factory(
        group=school6_group1,
        week_number=12,
        message_type=MessageType.INITIAL,
    )
    group_chat_transcript_factory(
        session=school6_group_session,
        sender=school6_group1_user1,
        role=BaseChatTranscript.Role.USER,
        content="Group message 1",
        created_at=transcript_date,
    )

    # Run the weekly summary generation
    generate_weekly_summaries()

    # Verify summaries were created for each school
    assert Summary.objects.count() == 6
    school1_summaries = list(Summary.objects.filter(school_name=school1).all())
    school2_summaries = list(Summary.objects.filter(school_name=school2).all())
    school3_summaries = list(Summary.objects.filter(school_name=school3).all())
    school4_summaries = list(Summary.objects.filter(school_name=school4).all())
    school5_summaries = list(Summary.objects.filter(school_name=school5).all())
    assert len(school1_summaries) == 2
    assert all(school_summaries.week_number == 5 for school_summaries in school1_summaries)
    assert school1_summaries[0].summary == "Summary 1"
    assert school1_summaries[1].summary == "Summary 2"
    assert len(school2_summaries) == 2
    assert len(school3_summaries) == 2
    assert len(school4_summaries) == 0
    assert len(school5_summaries) == 0

    # Assert that we called generate_top_10_summaries_for_school with the right chats
    all_call_args = school_1_mock_call = mock_generate_top_10_summaries_for_school.call_args_list
    school_1_mock_call = next(
        call for call in all_call_args if any(chat for chat in call[0][0] if chat.session.user.school_name == school1)
    )
    assert school_1_mock_call[0][0] == school1_included_individual_chats  # individual chats
    assert school_1_mock_call[0][1] == school1_included_group_chats  # group chats
    assert school_1_mock_call[0][2].week == 5  # sunday summary prompt

    # assert on logs
    assert "No summary prompt defined for week 12. Not generating summaries for school No Prompt School." in caplog.text

    # Run again and check that it doesn't create duplicates
    generate_weekly_summaries()
    assert Summary.objects.count() == 6


@freeze_time("2025-04-17T20:00:00")
@override_settings(BASE_ADMIN_URI="https://example.com/")
def test_notify_on_missing_summaries(
    user_factory,
    individual_session_factory,
    individual_chat_transcript_factory,
    sunday_summary_prompt_factory,
    summary_factory,
):
    transcript_date = timezone.make_aware(datetime.datetime(2025, 4, 15, 15, 0))
    sunday_summary_prompt_factory(week=5, activity="test_value")
    standard_user_group = AuthGroup.objects.get_or_create(name=AuthGroupName.StandardUser.value)
    standard_user1 = AuthUser.objects.create_user(
        username="standard_user1", password="password", email="standard_user1@example.net"
    )
    standard_user1.groups.add(standard_user_group[0])
    standard_user2 = AuthUser.objects.create_user(
        username="standard_user2", password="password", email="standard_user2@example.net"
    )
    standard_user2.groups.add(standard_user_group[0])
    AuthUser.objects.create_user(username="other_user1", password="password", email="other_user1@example.net")

    # School 1 - No chats since Monday so no summaries expected
    school1 = "No Recent Chats"
    school1_user = user_factory(school_name=school1)
    school1_session = individual_session_factory(user=school1_user, week_number=5, message_type=MessageType.INITIAL)
    individual_chat_transcript_factory(
        session=school1_session,
        role=BaseChatTranscript.Role.USER,
        created_at=transcript_date - datetime.timedelta(weeks=1),
    )

    # School 2 - Chats but no summary prompt for that week so no summaries expected
    school2 = "No Summary Prompt"
    school2_user = user_factory(school_name=school2)
    school2_session = individual_session_factory(user=school2_user, week_number=6, message_type=MessageType.INITIAL)
    individual_chat_transcript_factory(
        session=school2_session, role=BaseChatTranscript.Role.USER, created_at=transcript_date
    )

    # School 3 - Should have summaries but none generated
    school3 = "No Summaries"
    school3_user = user_factory(school_name=school3)
    school3_session = individual_session_factory(user=school3_user, week_number=5, message_type=MessageType.INITIAL)
    individual_chat_transcript_factory(
        session=school3_session, role=BaseChatTranscript.Role.USER, created_at=transcript_date
    )

    # School 4 - Has summaries but none selected
    school4 = "Unselected Summaries"
    school4_user = user_factory(school_name=school4)
    school4_session = individual_session_factory(user=school4_user, week_number=5, message_type=MessageType.INITIAL)
    individual_chat_transcript_factory(
        session=school4_session, role=BaseChatTranscript.Role.USER, created_at=transcript_date
    )
    summary_factory(school_name=school4, week_number=5, summary="Test summary", selected=False)
    summary_factory(school_name=school4, week_number=5, summary="Test summary", selected=False)

    # School 5 - Chats, prompt and selected summaries
    school5 = "Selected Summaries"
    school5_user = user_factory(school_name=school5)
    school5_session = individual_session_factory(user=school5_user, week_number=5, message_type=MessageType.INITIAL)
    individual_chat_transcript_factory(
        session=school5_session, role=BaseChatTranscript.Role.USER, created_at=transcript_date
    )
    summary_factory(school_name=school5, week_number=5, summary="Test summary", selected=False)
    summary_factory(school_name=school5, week_number=5, summary="Test summary", selected=True)

    # Run the notification check
    # Create a mock client with the post method returning the fake response.
    mock_client = MagicMock()
    with patch("chat.services.send.httpx.Client", return_value=get_client_patch(mock_client)):
        notify_on_missing_summaries()

    # Verify notifications were sent only for schools 3 and 4
    assert set(mock_client.post.call_args.kwargs["json"]["to_emails"]) == set(
        [
            "standard_user1@example.net",
            "standard_user2@example.net",
        ]
    )
    assert mock_client.post.call_args.kwargs["json"]["config_link"] == "https://example.com/admin/chat/summary/"
    assert set(mock_client.post.call_args.kwargs["json"]["missing_for"]) == set(
        [
            "No Summaries, week 5",
            "Unselected Summaries, week 5",
        ]
    )
