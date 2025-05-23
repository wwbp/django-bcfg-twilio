from unittest.mock import patch
import pytest
from django.utils import timezone

from chat.models import (
    BaseChatTranscript,
    GroupPipelineRecord,
    GroupPromptMessageType,
    GroupScheduledTaskAssociation,
    GroupStrategyPhase,
    GroupStrategyPhaseConfig,
    User,
)
from chat.services.group_pipeline import take_action_on_group


@pytest.fixture
def _mocks():
    with (
        patch(
            "chat.services.group_pipeline.send_message_to_participant_group", return_value={"status": "ok"}
        ) as mock_send_message_to_participant,
        patch(
            "chat.services.completion._generate_response", return_value=("LLM response", None, None)
        ) as mock_generate_response,
    ):
        yield mock_send_message_to_participant, mock_generate_response


@pytest.mark.parametrize(
    "current_strategy_phase",
    [
        GroupStrategyPhase.BEFORE_AUDIENCE,
        GroupStrategyPhase.AFTER_AUDIENCE,
        GroupStrategyPhase.AFTER_REMINDER,
        GroupStrategyPhase.AFTER_FOLLOWUP,
    ],
)
@pytest.mark.parametrize(
    "all_participants_responded,at_least_three_participants_responded", [[True, True], [False, True], [False, False]]
)
@pytest.mark.parametrize("reminder_message_sent", [True, False])
@pytest.mark.parametrize("summary_message_sent", [True, False])
def test_group_pipeline_take_action_on_group(
    _mocks,
    group_with_initial_message_interaction,
    current_strategy_phase,
    reminder_message_sent,
    summary_message_sent,
    all_participants_responded,
    at_least_three_participants_responded,
    group_chat_transcript_factory,
    group_prompt_factory,
    control_prompts,
):
    GroupStrategyPhaseConfig.objects.all().delete()
    GroupStrategyPhaseConfig.objects.create(
        group_strategy_phase=GroupStrategyPhase.AFTER_AUDIENCE,
        min_wait_seconds=1,
        max_wait_seconds=2,
    )
    GroupStrategyPhaseConfig.objects.create(
        group_strategy_phase=GroupStrategyPhase.AFTER_REMINDER,
        min_wait_seconds=3,
        max_wait_seconds=4,
    )
    GroupStrategyPhaseConfig.objects.create(
        group_strategy_phase=GroupStrategyPhase.AFTER_FOLLOWUP,
        min_wait_seconds=5,
        max_wait_seconds=6,
    )
    mock_send_message_to_participant, _ = _mocks
    group, session, group_pipeline_record, _ = group_with_initial_message_interaction
    most_recent_chat_transcript = session.transcripts.order_by("-created_at").first()
    session.current_strategy_phase = current_strategy_phase
    session.save()
    if reminder_message_sent:
        group_chat_transcript_factory(
            session=session,
            moderation_status=BaseChatTranscript.ModerationStatus.NOT_FLAGGED,
            assistant_strategy_phase=GroupStrategyPhase.REMINDER,
            role=BaseChatTranscript.Role.ASSISTANT,
            content="Reminder message",
        )
    if summary_message_sent:
        group_chat_transcript_factory(
            session=session,
            moderation_status=BaseChatTranscript.ModerationStatus.NOT_FLAGGED,
            assistant_strategy_phase=GroupStrategyPhase.SUMMARY,
            role=BaseChatTranscript.Role.ASSISTANT,
            content="Summary message",
        )
    group_users = group.users.all()
    if all_participants_responded:
        for user in group_users:
            group_chat_transcript_factory(
                session=session,
                moderation_status=BaseChatTranscript.ModerationStatus.NOT_FLAGGED,
                role=BaseChatTranscript.Role.USER,
                content="User response",
                sender=user,
            )
    elif at_least_three_participants_responded:
        for i in range(3):
            group_chat_transcript_factory(
                session=session,
                moderation_status=BaseChatTranscript.ModerationStatus.NOT_FLAGGED,
                role=BaseChatTranscript.Role.USER,
                content="User response",
                sender=group_users[i],
            )
    starting_transcript_count = session.transcripts.count()
    group_prompt_factory(week=1, activity="activity", strategy_type=GroupStrategyPhase.FOLLOWUP)
    group_prompt_factory(week=1, activity="activity", strategy_type=GroupStrategyPhase.SUMMARY)
    take_action_on_group(group_pipeline_record.run_id, most_recent_chat_transcript.id)

    session.refresh_from_db()
    group_pipeline_record.refresh_from_db()
    most_recent_chat_transcript = session.transcripts.order_by("-created_at").first()

    # assert that correct message and scheduling actions were taken
    match current_strategy_phase:
        case GroupStrategyPhase.BEFORE_AUDIENCE | GroupStrategyPhase.AFTER_AUDIENCE | GroupStrategyPhase.AFTER_REMINDER:
            # for these cases, we always send a message and schedule another action
            assert group_pipeline_record.status == GroupPipelineRecord.StageStatus.SCHEDULED_ACTION
            assert GroupScheduledTaskAssociation.objects.count() == 1
            assert session.transcripts.count() == starting_transcript_count + 1
            assert mock_send_message_to_participant.call_count == 1

            # we can do this here because we assert that session.current_strategy_phase is correct below
            config = GroupStrategyPhaseConfig.objects.get(group_strategy_phase=session.current_strategy_phase)
            task_clocked_time = GroupScheduledTaskAssociation.objects.get().task.clocked.clocked_time
            assert task_clocked_time > timezone.now() + timezone.timedelta(seconds=config.min_wait_seconds - 1)
            assert task_clocked_time <= timezone.now() + timezone.timedelta(seconds=config.max_wait_seconds)
        case GroupStrategyPhase.AFTER_FOLLOWUP:
            # for this case, we conditionally send a message and never schedule another action
            assert GroupScheduledTaskAssociation.objects.count() == 0
            if not at_least_three_participants_responded:
                assert group_pipeline_record.status == GroupPipelineRecord.StageStatus.PROCESS_NOTHING_TO_DO
                assert mock_send_message_to_participant.call_count == 0
            elif summary_message_sent:
                assert group_pipeline_record.status == GroupPipelineRecord.StageStatus.PROCESS_NOTHING_TO_DO
                assert mock_send_message_to_participant.call_count == 0
            else:
                assert group_pipeline_record.status == GroupPipelineRecord.StageStatus.SEND_PASSED
                assert mock_send_message_to_participant.call_count == 1

    # assert that we moved to the correct phase and sent the correct message (if one was sent)
    if current_strategy_phase == GroupStrategyPhase.BEFORE_AUDIENCE:
        assert session.current_strategy_phase == GroupStrategyPhase.AFTER_AUDIENCE
        assert most_recent_chat_transcript.assistant_strategy_phase == GroupStrategyPhase.AUDIENCE
    elif current_strategy_phase == GroupStrategyPhase.AFTER_AUDIENCE:
        if reminder_message_sent:
            assert session.current_strategy_phase == GroupStrategyPhase.AFTER_FOLLOWUP
            assert most_recent_chat_transcript.assistant_strategy_phase == GroupStrategyPhase.FOLLOWUP
        elif all_participants_responded:
            assert session.current_strategy_phase == GroupStrategyPhase.AFTER_FOLLOWUP
            assert most_recent_chat_transcript.assistant_strategy_phase == GroupStrategyPhase.FOLLOWUP
        else:
            assert session.current_strategy_phase == GroupStrategyPhase.AFTER_REMINDER
            assert most_recent_chat_transcript.assistant_strategy_phase == GroupStrategyPhase.REMINDER
    elif current_strategy_phase == GroupStrategyPhase.AFTER_REMINDER:
        assert session.current_strategy_phase == GroupStrategyPhase.AFTER_FOLLOWUP
        assert most_recent_chat_transcript.assistant_strategy_phase == GroupStrategyPhase.FOLLOWUP
    elif current_strategy_phase == GroupStrategyPhase.AFTER_FOLLOWUP:
        assert session.current_strategy_phase == GroupStrategyPhase.AFTER_SUMMARY
        if mock_send_message_to_participant.call_count == 1:
            assert most_recent_chat_transcript.assistant_strategy_phase == GroupStrategyPhase.SUMMARY


def test_group_pipeline_take_action_on_group_throws_exception_if_after_summary_phase(
    _mocks,
    group_with_initial_message_interaction,
    caplog,
):
    _, session, group_pipeline_record, _ = group_with_initial_message_interaction
    most_recent_chat_transcript = session.transcripts.order_by("-created_at").first()
    session.current_strategy_phase = GroupStrategyPhase.AFTER_SUMMARY
    session.save()

    with pytest.raises(ValueError) as e:
        take_action_on_group(group_pipeline_record.run_id, most_recent_chat_transcript.id)

    group_pipeline_record.refresh_from_db()
    assert "No messages to be sent in strategy phase" in str(e.value)
    assert group_pipeline_record.status == GroupPipelineRecord.StageStatus.FAILED
    assert group_pipeline_record.error_log == str(e.value)
    assert "Action on group failed for group" in caplog.text
    assert "No messages to be sent in strategy phase" in caplog.text


def test_group_pipeline_take_action_on_group_not_latest_action_on_start(
    group_with_initial_message_interaction, group_pipeline_record_factory, _mocks
):
    group, session, group_pipeline_record, _ = group_with_initial_message_interaction
    most_recent_chat_transcript = session.transcripts.order_by("-created_at").first()
    mock_send_message_to_participant, _ = _mocks
    group_pipeline_record_factory(
        group=group,
        user=group.users.first(),
        status=GroupPipelineRecord.StageStatus.INGEST_PASSED,
        message="some other message sent by a user",
        response=None,
        instruction_prompt=None,
        validated_message=None,
        error_log=None,
    )

    take_action_on_group(group_pipeline_record.run_id, most_recent_chat_transcript.id)

    group_pipeline_record.refresh_from_db()
    assert group_pipeline_record.status == GroupPipelineRecord.StageStatus.PROCESS_SKIPPED
    assert mock_send_message_to_participant.call_count == 0


@patch("chat.services.group_pipeline._compute_and_validate_message_to_send")
def test_group_pipeline_take_action_on_group_not_latest_action_after_compute_response(
    mock_compute_and_validate_message_to_send,
    group_with_initial_message_interaction,
    group_pipeline_record_factory,
    _mocks,
):
    group, session, group_pipeline_record, _ = group_with_initial_message_interaction
    most_recent_chat_transcript = session.transcripts.order_by("-created_at").first()
    mock_send_message_to_participant, _ = _mocks

    def _compute_and_validate_message_to_send_side_effect(*args, **kwargs):
        # mock new message comes in here
        group_pipeline_record_factory(
            group=group,
            user=group.users.first(),
            status=GroupPipelineRecord.StageStatus.INGEST_PASSED,
            message="some other message sent by a user",
            response=None,
            instruction_prompt=None,
            validated_message=None,
            error_log=None,
        )

    mock_compute_and_validate_message_to_send.side_effect = _compute_and_validate_message_to_send_side_effect

    take_action_on_group(group_pipeline_record.run_id, most_recent_chat_transcript.id)

    group_pipeline_record.refresh_from_db()
    assert group_pipeline_record.status == GroupPipelineRecord.StageStatus.PROCESS_SKIPPED
    assert mock_send_message_to_participant.call_count == 0


def test_audience_action_loads_instruction_prompt_and_schedules(
    _mocks, group_with_initial_message_interaction, group_prompt_factory, control_prompts
):
    mock_send, _ = _mocks
    group, session, record, _ = group_with_initial_message_interaction

    # start at BEFORE_AUDIENCE
    session.current_strategy_phase = GroupStrategyPhase.BEFORE_AUDIENCE
    session.save()

    # use the most‐recent user transcript as trigger
    trigger = session.transcripts.order_by("-created_at").first()

    take_action_on_group(record.run_id, trigger.id)

    record.refresh_from_db()
    assert record.response == "LLM response"
    assert record.validated_message == "LLM response"
    assert "<<GROUP AUDIENCE PROMPT>>" in record.instruction_prompt


def test_followup_action_assistant_after_audience_no_reminder(
    _mocks, group_with_initial_message_interaction, group_prompt_factory, group_chat_transcript_factory, control_prompts
):
    mock_send, _ = _mocks
    group, session, record, _ = group_with_initial_message_interaction
    group_chat_transcript_factory(
        session=session,
        role=BaseChatTranscript.Role.ASSISTANT,
        content="user_message",
        assistant_strategy_phase=GroupStrategyPhase.REMINDER,
    )
    group_prompt_factory(week=1, activity="<<INSTRUCTION FOR FOLLOWUP>>", strategy_type=GroupStrategyPhase.FOLLOWUP)
    # start at BEFORE_AUDIENCE
    session.current_strategy_phase = GroupStrategyPhase.AFTER_AUDIENCE
    session.save()

    # use the most‐recent user transcript as trigger
    trigger = session.transcripts.order_by("-created_at").first()

    # 1 previous reminder
    # should not trigger reminder
    take_action_on_group(record.run_id, trigger.id)

    record.refresh_from_db()
    assert record.response == "LLM response"
    assert record.validated_message == "LLM response"
    assert "<<INSTRUCTION FOR FOLLOWUP>>" in record.instruction_prompt


def test_followup_action_assistant_after_reminder(
    _mocks, group_with_initial_message_interaction, group_prompt_factory, control_prompts
):
    mock_send, _ = _mocks
    group, session, record, _ = group_with_initial_message_interaction
    group_prompt_factory(week=1, activity="<<INSTRUCTION FOR FOLLOWUP>>", strategy_type=GroupStrategyPhase.FOLLOWUP)
    # start at BEFORE_AUDIENCE
    session.current_strategy_phase = GroupStrategyPhase.AFTER_REMINDER
    session.save()

    # use the most‐recent user transcript as trigger
    trigger = session.transcripts.order_by("-created_at").first()

    take_action_on_group(record.run_id, trigger.id)

    record.refresh_from_db()
    assert record.response == "LLM response"
    assert record.validated_message == "LLM response"
    assert "<<INSTRUCTION FOR FOLLOWUP>>" in record.instruction_prompt


def test_summary_action_loads_instruction_prompt_and_schedules(
    _mocks,
    group_with_initial_message_interaction,
    group_prompt_factory,
    group_chat_transcript_factory,
    control_prompts,
):
    mock_send, _ = _mocks
    group, session, record, _ = group_with_initial_message_interaction
    users = User.objects.filter(group=group)
    for user in users:
        group_chat_transcript_factory(
            session=session,
            role=BaseChatTranscript.Role.USER,
            content="User response",
            sender=user,
        )
    group_prompt_factory(week=1, activity="<<INSTRUCTION FOR SUMMARY>>", strategy_type=GroupStrategyPhase.SUMMARY)

    # start at AFTER_FOLLOWUP
    session.current_strategy_phase = GroupStrategyPhase.AFTER_FOLLOWUP
    session.save()

    # use the most‐recent user transcript as trigger
    trigger = session.transcripts.order_by("-created_at").first()

    # all participants +3 interacted, should trigger summary
    take_action_on_group(record.run_id, trigger.id)

    record.refresh_from_db()
    assert record.response == "LLM response"
    assert record.validated_message == "LLM response"
    assert "<<INSTRUCTION FOR SUMMARY>>" in record.instruction_prompt
    assert "<<GROUP SUMMARY PERSONA PROMPT>>" in record.instruction_prompt
    assert "<<PERSONA PROMPT>>" not in record.instruction_prompt


def test_no_summary_action_one_participant_interacted(
    _mocks, group_with_initial_message_interaction, group_prompt_factory, control_prompts
):
    mock_send, _ = _mocks
    group, session, record, _ = group_with_initial_message_interaction
    group_prompt_factory(week=1, activity="<<INSTRUCTION FOR SUMMARY>>", strategy_type=GroupStrategyPhase.SUMMARY)

    # start at AFTER_FOLLOWUP
    session.current_strategy_phase = GroupStrategyPhase.AFTER_FOLLOWUP
    session.save()

    # use the most‐recent user transcript as trigger
    trigger = session.transcripts.order_by("-created_at").first()

    # less than 3 participant interacted, should not trigger summary
    take_action_on_group(record.run_id, trigger.id)

    record.refresh_from_db()
    session.refresh_from_db()
    assert session.current_strategy_phase == GroupStrategyPhase.AFTER_SUMMARY
    assert record.status == GroupPipelineRecord.StageStatus.PROCESS_NOTHING_TO_DO


def test_no_summary_action_sent_once(
    _mocks,
    group_with_initial_message_interaction,
    group_prompt_factory,
    group_chat_transcript_factory,
    control_prompts,
):
    mock_send, _ = _mocks
    group, session, record, _ = group_with_initial_message_interaction
    group_chat_transcript_factory(
        session=session,
        role=BaseChatTranscript.Role.ASSISTANT,
        content="user_message",
        assistant_strategy_phase=GroupStrategyPhase.SUMMARY,
    )
    group_prompt_factory(week=1, activity="<<INSTRUCTION FOR SUMMARY>>", strategy_type=GroupStrategyPhase.SUMMARY)

    # start at AFTER_FOLLOWUP
    session.current_strategy_phase = GroupStrategyPhase.AFTER_FOLLOWUP
    session.save()

    # use the most‐recent user transcript as trigger
    trigger = session.transcripts.order_by("-created_at").first()

    # less than 3 participant interacted, should not trigger summary
    take_action_on_group(record.run_id, trigger.id)

    record.refresh_from_db()
    session.refresh_from_db()
    assert session.current_strategy_phase == GroupStrategyPhase.AFTER_SUMMARY
    assert record.status == GroupPipelineRecord.StageStatus.PROCESS_NOTHING_TO_DO


def test_reminder_action_loads_instruction_prompt_and_schedules(
    _mocks, group_with_initial_message_interaction, group_prompt_factory, control_prompts
):
    mock_send, _ = _mocks
    group, session, record, _ = group_with_initial_message_interaction

    # start at BEFORE_AUDIENCE
    session.current_strategy_phase = GroupStrategyPhase.AFTER_AUDIENCE
    session.save()

    # use the most‐recent user transcript as trigger
    trigger = session.transcripts.order_by("-created_at").first()

    # group has 6 user with one user messsage and no previous reminders
    # should trigger reminder
    take_action_on_group(record.run_id, trigger.id)

    record.refresh_from_db()
    assert record.response == "LLM response"
    assert record.validated_message == "LLM response"
    assert "<<REMINDER PROMPT>>" in record.instruction_prompt


def test_no_reminder_action_all_user_responded(
    _mocks,
    group_with_initial_message_interaction,
    group_prompt_factory,
    group_chat_transcript_factory,
    control_prompts,
):
    mock_send, _ = _mocks
    group, session, record, _ = group_with_initial_message_interaction
    users = User.objects.filter(group=group)
    for user in users:
        group_chat_transcript_factory(
            session=session, role=BaseChatTranscript.Role.USER, content="user_message", sender=user
        )
    group_prompt_factory(week=1, activity="<<INSTRUCTION FOR FOLLOWUP>>", strategy_type=GroupStrategyPhase.FOLLOWUP)
    # start at BEFORE_AUDIENCE
    session.current_strategy_phase = GroupStrategyPhase.AFTER_AUDIENCE
    session.save()

    # use the most‐recent user transcript as trigger
    trigger = session.transcripts.order_by("-created_at").first()

    # group has 6 user with all users responding and no previous reminders
    # should not trigger reminder
    take_action_on_group(record.run_id, trigger.id)

    record.refresh_from_db()
    assert record.response == "LLM response"
    assert record.validated_message == "LLM response"
    assert "<<REMINDER PROMPT>>" not in record.instruction_prompt
    assert "<<INSTRUCTION FOR FOLLOWUP>>" in record.instruction_prompt


def test_no_reminder_action_assistant_sent_one(
    _mocks,
    group_with_initial_message_interaction,
    group_prompt_factory,
    group_chat_transcript_factory,
    control_prompts,
):
    mock_send, _ = _mocks
    group, session, record, _ = group_with_initial_message_interaction
    group_chat_transcript_factory(
        session=session,
        role=BaseChatTranscript.Role.ASSISTANT,
        content="user_message",
        assistant_strategy_phase=GroupStrategyPhase.REMINDER,
    )
    group_prompt_factory(week=1, activity="<<INSTRUCTION FOR FOLLOWUP>>", strategy_type=GroupStrategyPhase.FOLLOWUP)
    # start at BEFORE_AUDIENCE
    session.current_strategy_phase = GroupStrategyPhase.AFTER_AUDIENCE
    session.save()

    # use the most‐recent user transcript as trigger
    trigger = session.transcripts.order_by("-created_at").first()

    # 1 previous reminder
    # should not trigger reminder
    take_action_on_group(record.run_id, trigger.id)

    record.refresh_from_db()
    assert record.response == "LLM response"
    assert record.validated_message == "LLM response"
    assert "<<REMINDER PROMPT>>" not in record.instruction_prompt
    assert "<<INSTRUCTION FOR FOLLOWUP>>" in record.instruction_prompt


def test_after_audience_skips_reminder_when_message_type_summary(
    _mocks,
    group_with_initial_message_interaction,
    group_prompt_factory,
    control_prompts,
):
    """
    If session.message_type == SUMMARY in AFTER_AUDIENCE, we must skip the reminder
    and go straight to FOLLOWUP.
    """
    mock_send, _ = _mocks
    group, session, record, _ = group_with_initial_message_interaction

    # set up phase and message_type
    session.current_strategy_phase = GroupStrategyPhase.AFTER_AUDIENCE
    session.message_type = GroupPromptMessageType.SUMMARY
    session.save()

    # ensure there's a followup prompt available
    group_prompt_factory(
        week=1,
        message_type=GroupPromptMessageType.SUMMARY,
        activity="<<FOLLOWUP PROMPT>>",
        strategy_type=GroupStrategyPhase.FOLLOWUP,
    )

    trigger = session.transcripts.order_by("-created_at").first()
    take_action_on_group(record.run_id, trigger.id)

    record.refresh_from_db()
    session.refresh_from_db()

    # we should have sent a FOLLOWUP, not a REMINDER
    assert record.status == GroupPipelineRecord.StageStatus.SCHEDULED_ACTION
    assert mock_send.call_count == 1
    assert "<<FOLLOWUP PROMPT>>" in record.instruction_prompt
    assert session.current_strategy_phase == GroupStrategyPhase.AFTER_FOLLOWUP


def test_after_followup_skips_summary_when_message_type_summary(
    _mocks,
    group_with_initial_message_interaction,
):
    """
    If session.message_type == SUMMARY in AFTER_FOLLOWUP, we must skip SUMMARY
    altogether and move to AFTER_SUMMARY with no message sent.
    """
    mock_send, _ = _mocks
    group, session, record, _ = group_with_initial_message_interaction

    # set up phase and message_type
    session.current_strategy_phase = GroupStrategyPhase.AFTER_FOLLOWUP
    session.message_type = GroupPromptMessageType.SUMMARY
    session.save()

    trigger = session.transcripts.order_by("-created_at").first()
    take_action_on_group(record.run_id, trigger.id)

    record.refresh_from_db()
    session.refresh_from_db()

    # no summary should be sent, and we should end up in AFTER_SUMMARY
    assert record.status == GroupPipelineRecord.StageStatus.PROCESS_NOTHING_TO_DO
    assert mock_send.call_count == 0
    assert session.current_strategy_phase == GroupStrategyPhase.AFTER_SUMMARY
