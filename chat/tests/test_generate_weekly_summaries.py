import datetime
from unittest.mock import patch
from freezegun import freeze_time
from django.utils import timezone
from chat.models import (
    BaseChatTranscript,
    MessageType,
    Summary,
)
from chat.services.summaries import generate_weekly_summaries


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
):
    mock_generate_top_10_summaries_for_school.return_value = ["Summary 1", "Summary 2"]
    school1 = "Group and Indiv School"
    school2 = "Indiv Only School"
    school3 = "Group Only School"
    school4 = "Test School"
    school5 = "Old School"
    transcript_date = timezone.make_aware(datetime.datetime(2025, 4, 15, 15, 0))
    old_transcript_date = timezone.make_aware(datetime.datetime(2025, 4, 8, 15, 0))

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
    school_1_mock_call = next(call for call in all_call_args if call[0][0] == school1)
    assert school_1_mock_call[0][1] == 5
    assert school_1_mock_call[0][2] == school1_included_individual_chats
    assert school_1_mock_call[0][3] == school1_included_group_chats

    # Run again and check that it doesn't create duplicates
    generate_weekly_summaries()
    assert Summary.objects.count() == 6
