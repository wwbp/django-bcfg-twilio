# group_pipeline.py
import json
import logging
import random
from celery import shared_task
from chat.services.individual_crud import format_chat_history, strip_meta
from django_celery_beat.models import PeriodicTask, ClockedSchedule
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from chat.serializers import (
    GroupIncomingInitialMessage,
    GroupIncomingMessage,
    GroupIncomingMessageSerializer,
    GroupIncomingInitialMessageSerializer,
)
from chat.services.completion import ensure_within_character_limit, generate_response
from chat.services.group_crud import (
    ingest_initial_message,
    load_group_chat_history,
    load_instruction_prompt,
    ingest_request,
)
from chat.services.moderation import moderate_message
from chat.services.send import send_message_to_participant_group

from ..models import (
    BaseChatTranscript,
    GroupChatTranscript,
    GroupPipelineRecord,
    GroupPromptMessageType,
    GroupScheduledTaskAssociation,
    GroupSession,
    GroupStrategyPhase,
    GroupStrategyPhaseConfig,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Pipeline Functions
# =============================================================================

_FALLBACK_DELAY_WITHOUT_CONFIG_SECONDS = 60


def _newer_user_messages_exist(record: GroupPipelineRecord):
    latest_record_for_group = GroupPipelineRecord.objects.filter(group=record.group).order_by("-created_at").first()
    newer_message_exists = record != latest_record_for_group
    if newer_message_exists:
        record.status = GroupPipelineRecord.StageStatus.PROCESS_SKIPPED
        record.save()
    return newer_message_exists


def _ingest(
    group_id: str, group_incoming_message: GroupIncomingMessage
) -> tuple[GroupPipelineRecord, GroupChatTranscript]:
    """
    Stage 1: Validate and store incoming data, then create a new run record.
    """
    group, user_chat_transcript = ingest_request(group_id, group_incoming_message)
    record = GroupPipelineRecord.objects.create(
        user=user_chat_transcript.sender,
        group=group,
        message=group_incoming_message.message,
        status=GroupPipelineRecord.StageStatus.INGEST_PASSED,
    )
    logger.info(f"Group ingest pipeline complete for group {group_id}, run_id {record.run_id}")
    return record, user_chat_transcript


def _moderate(record: GroupPipelineRecord, user_chat_transcript: GroupChatTranscript):
    """
    Stage 2: Moderate the incoming message before processing.
    """
    message = record.message
    blocked_str = moderate_message(message)
    if blocked_str:
        user_chat_transcript.moderation_status = GroupChatTranscript.ModerationStatus.FLAGGED
        record.status = GroupPipelineRecord.StageStatus.MODERATION_BLOCKED
    else:
        user_chat_transcript.moderation_status = GroupChatTranscript.ModerationStatus.NOT_FLAGGED
        record.status = GroupPipelineRecord.StageStatus.MODERATION_PASSED
    record.save()
    user_chat_transcript.save()
    logger.info(
        f"Group moderation pipeline complete for group {record.group.id}, "
        f"sender {record.user.id}, run_id {record.run_id}"
    )


def _get_send_message_delay_seconds(user_chat_transcript: GroupChatTranscript) -> int:
    if user_chat_transcript.session.group.is_test:
        # enable faster testing
        return 1
    try:
        phase_config = GroupStrategyPhaseConfig.objects.get(
            group_strategy_phase=user_chat_transcript.session.current_strategy_phase
        )
        if phase_config.min_wait_seconds == phase_config.max_wait_seconds:
            return phase_config.min_wait_seconds
        return random.randint(phase_config.min_wait_seconds, phase_config.max_wait_seconds)
    except GroupStrategyPhaseConfig.DoesNotExist:
        logger.error(
            f"Group strategy phase config not found for phase '{user_chat_transcript.session.current_strategy_phase}'"
        )
        return _FALLBACK_DELAY_WITHOUT_CONFIG_SECONDS


def _clear_existing_and_schedule_group_action(
    last_user_chat_transcript: GroupChatTranscript, record: GroupPipelineRecord
):
    delay_sec = _get_send_message_delay_seconds(last_user_chat_transcript)
    with transaction.atomic():
        # delete existing tasks
        GroupScheduledTaskAssociation.objects.filter(group=record.group).delete()

        # create new associations and tasks
        clocked_time = timezone.now() + timezone.timedelta(seconds=delay_sec)
        interval, _ = ClockedSchedule.objects.get_or_create(clocked_time=clocked_time)
        task = PeriodicTask.objects.create(
            name=f"Respond to chat {last_user_chat_transcript.id} (group {record.group.id})",
            task="chat.services.group_pipeline.take_action_on_group",
            clocked=interval,
            kwargs=json.dumps({"user_chat_transcript_id": last_user_chat_transcript.id, "run_id": str(record.run_id)}),
            one_off=True,
        )
        GroupScheduledTaskAssociation.objects.create(group=record.group, task=task)
        record.status = GroupPipelineRecord.StageStatus.SCHEDULED_ACTION
        record.save()
    logger.info(
        f"Scheduled response for group {record.group.id} "
        f"(phase {last_user_chat_transcript.session.current_strategy_phase}), "
        f"sender {record.user.id}, run_id {record.run_id} "
        f"after {delay_sec} seconds"
    )


def _compute_and_validate_message_to_send(
    record: GroupPipelineRecord, session: GroupSession, next_strategy_phase: GroupStrategyPhase
):
    # generate response
    # # load instruction prompt given strategy
    instruction_prompt = load_instruction_prompt(session, next_strategy_phase)
    chat_history, message = load_group_chat_history(session)
    start_timer = timezone.now()
    gpt_model = record.group.gpt_model or settings.OPENAI_MODEL
    response, prompt_tokens, completion_tokens = generate_response(chat_history, instruction_prompt, message, gpt_model)
    # Strip metadata from the response if the user is not a test user
    # for testing llm responses, we want to see the raw response
    if not record.is_test:
        response = strip_meta(response, record.user.school_mascot)
    record.prompt_tokens = prompt_tokens
    record.completion_tokens = completion_tokens
    record.gpt_model = gpt_model
    record.processed_message = message
    record.latency = timezone.now() - start_timer
    record.instruction_prompt = instruction_prompt
    record.chat_history = format_chat_history(chat_history)
    record.response = response
    # validate response
    # ensure 320 characters or less
    record.validated_message = ensure_within_character_limit(record)

    record.status = GroupPipelineRecord.StageStatus.PROCESS_PASSED
    record.save()


def _save_and_send_message(record: GroupPipelineRecord, session: GroupSession, next_strategy_phase: GroupStrategyPhase):
    """
    Stage 5: Retrieve the most recent response and send it to the participant.
    """
    group_id = record.group.id
    response = record.validated_message
    record.transcript = GroupChatTranscript.objects.create(
        session=session,
        role=BaseChatTranscript.Role.ASSISTANT,
        content=response,
        instruction_prompt=record.instruction_prompt,
        chat_history=record.chat_history,
        latency=record.latency,
        shorten_count=record.shorten_count,
        user_message=record.processed_message,
        assistant_strategy_phase=next_strategy_phase,
    )
    if not record.is_test and response:
        send_message_to_participant_group(group_id, response)
        record.status = GroupPipelineRecord.StageStatus.SEND_PASSED
    record.save()
    logger.info(
        f"Group send pipeline complete for group {record.group.id}, sender {record.user.id}, run_id {record.run_id}"
    )


# =============================================================================
# Celery Tasks: Tie the Stages Together
# =============================================================================


@shared_task
def handle_inbound_group_initial_message(group_id: str, data: dict):
    serializer = GroupIncomingInitialMessageSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    group_incoming_initial_message: GroupIncomingInitialMessage = serializer.validated_data
    ingest_initial_message(group_id, group_incoming_initial_message)


@shared_task
def handle_inbound_group_message(group_id: str, data: dict):
    # we reuse serializer used in inbound http endpoint, which already validated data
    serializer = GroupIncomingMessageSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    group_incoming_message: GroupIncomingMessage = serializer.validated_data

    record: GroupPipelineRecord | None = None
    try:
        # ingest
        record, user_chat_transcript = _ingest(group_id, group_incoming_message)

        # moderate
        _moderate(record, user_chat_transcript)
        if record.status == GroupPipelineRecord.StageStatus.MODERATION_BLOCKED:
            return

        # handle changing current session if necessary
        #   all phases revert back to BEFORE_AUDIENCE when a message is received except for AFTER_AUDIENCE,
        #   which stays on itself while messages are still being received
        if user_chat_transcript.session.current_strategy_phase not in [
            GroupStrategyPhase.BEFORE_AUDIENCE,
            GroupStrategyPhase.AFTER_AUDIENCE,
        ]:
            user_chat_transcript.session.current_strategy_phase = GroupStrategyPhase.BEFORE_AUDIENCE
            user_chat_transcript.session.save()

        # schedule response
        if _newer_user_messages_exist(record):
            return
        _clear_existing_and_schedule_group_action(user_chat_transcript, record)
    except Exception as exc:
        if record:
            record.status = GroupPipelineRecord.StageStatus.FAILED
            record.error_log = str(exc)
            record.save()
        logger.exception(f"Group pipeline ingestion failed for group {group_id}")
        raise


@shared_task
def take_action_on_group(run_id: str, user_chat_transcript_id: int):
    """
    Stage 3: Send the response to the group.
    """
    record = GroupPipelineRecord.objects.get(run_id=run_id)
    try:
        user_chat_transcript = GroupChatTranscript.objects.get(id=user_chat_transcript_id)
        session = user_chat_transcript.session
        if _newer_user_messages_exist(record):
            return

        def should_skip_reminder(session) -> bool:
            return (
                session.message_type == GroupPromptMessageType.SUMMARY
                or session.all_participants_responded
                or session.reminder_sent
            )

        def should_skip_summary(session) -> bool:
            return (
                session.message_type == GroupPromptMessageType.SUMMARY
                or session.fewer_than_three_participants_responded
                or session.summary_sent
            )

        # figure out what action we should take
        next_strategy_phase: GroupStrategyPhase
        match session.current_strategy_phase:
            case GroupStrategyPhase.BEFORE_AUDIENCE:
                next_strategy_phase = GroupStrategyPhase.AUDIENCE  # type: ignore[assignment]
            case GroupStrategyPhase.AFTER_AUDIENCE:
                next_strategy_phase = (
                    GroupStrategyPhase.FOLLOWUP if should_skip_reminder(session) else GroupStrategyPhase.REMINDER  # type: ignore[assignment]
                )
            case GroupStrategyPhase.AFTER_REMINDER:
                next_strategy_phase = GroupStrategyPhase.FOLLOWUP  # type: ignore[assignment]
            case GroupStrategyPhase.AFTER_FOLLOWUP:
                next_strategy_phase = (
                    GroupStrategyPhase.AFTER_SUMMARY if should_skip_summary(session) else GroupStrategyPhase.SUMMARY  # type: ignore[assignment]
                )
            case GroupStrategyPhase.AFTER_SUMMARY:
                raise ValueError(
                    f"No messages to be sent in strategy phase {user_chat_transcript.session.current_strategy_phase}. "
                    "How did we get here?"
                )

        # take the action
        if next_strategy_phase == GroupStrategyPhase.AFTER_SUMMARY:
            # nothing to do
            record.status = GroupPipelineRecord.StageStatus.PROCESS_NOTHING_TO_DO
            record.save()
        else:
            _compute_and_validate_message_to_send(record, session, next_strategy_phase)
            if _newer_user_messages_exist(record):
                # computing message takes some time, a new message may have come in since
                # in which case, we do not want to take action or move to the next phase
                # as the new message will take precedence
                return
            _save_and_send_message(record, session, next_strategy_phase)

        # move to the next phase
        match next_strategy_phase:
            case GroupStrategyPhase.AUDIENCE:
                session.current_strategy_phase = GroupStrategyPhase.AFTER_AUDIENCE
            case GroupStrategyPhase.REMINDER:
                session.current_strategy_phase = GroupStrategyPhase.AFTER_REMINDER
            case GroupStrategyPhase.FOLLOWUP:
                session.current_strategy_phase = GroupStrategyPhase.AFTER_FOLLOWUP
            case GroupStrategyPhase.SUMMARY | GroupStrategyPhase.AFTER_SUMMARY:
                session.current_strategy_phase = GroupStrategyPhase.AFTER_SUMMARY
        session.save()
        if session.current_strategy_phase != GroupStrategyPhase.AFTER_SUMMARY:
            _clear_existing_and_schedule_group_action(user_chat_transcript, record)

        logger.info(
            f"Group action complete for group {record.group.id}, sender {record.user.id}, run_id {record.run_id}"
        )
    except Exception as exc:
        record.status = GroupPipelineRecord.StageStatus.FAILED
        record.error_log = str(exc)
        record.save()
        logger.exception(f"Action on group failed for group {record.group.id}")
        raise
