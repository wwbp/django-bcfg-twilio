import logging
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from chat.serializers import (
    IndividualIncomingMessage,
    IndividualIncomingMessageSerializer,
)
from .moderation import moderate_message
from .individual_crud import (
    format_chat_history,
    load_individual_and_group_chat_history_for_direct_messaging,
    load_individual_chat_history,
    load_instruction_prompt,
    ingest_request,
    load_instruction_prompt_for_direct_messaging,
    save_assistant_response,
    strip_meta,
    ingest_initial_message,
)
from .completion import ensure_within_character_limit, generate_response
from .send import send_moderation_message, send_message_to_participant
from ..models import (
    IndividualChatTranscript,
    IndividualPipelineRecord,
    IndividualSession,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Pipeline Functions
# =============================================================================


def _newer_user_messages_exist(record: IndividualPipelineRecord):
    latest_record_for_user = IndividualPipelineRecord.objects.filter(user=record.user).order_by("-created_at").first()
    newer_message_exists = record != latest_record_for_user
    if newer_message_exists:
        record.status = IndividualPipelineRecord.StageStatus.PROCESS_SKIPPED
        record.save()
    return newer_message_exists


def individual_ingest(participant_id: str, individual_incoming_message: IndividualIncomingMessage):
    """
    Stage 1: Validate and store incoming data, then create a new run record.
    """
    user, session, user_chat_transcript = ingest_request(participant_id, individual_incoming_message)
    record = IndividualPipelineRecord.objects.create(
        user=user,
        message=individual_incoming_message.message,
        status=IndividualPipelineRecord.StageStatus.INGEST_PASSED,
        is_for_group_direct_messaging=user.group is not None,
    )
    logger.info(f"Individual ingest pipeline complete for participant {participant_id}, run_id {record.run_id}")
    if record.is_for_group_direct_messaging:
        logger.info(f"User {user.id} is in group {user.group.id}, using group direct-message strategy.")
    return record, session, user_chat_transcript


def individual_moderation(record: IndividualPipelineRecord, user_chat_transcript: IndividualChatTranscript):
    """
    Stage 2: Moderate the incoming message before processing.
    """
    message = record.message
    blocked_str = moderate_message(message)
    if blocked_str:
        user_chat_transcript.moderation_status = IndividualChatTranscript.ModerationStatus.FLAGGED
        record.status = IndividualPipelineRecord.StageStatus.MODERATION_BLOCKED
    else:
        user_chat_transcript.moderation_status = IndividualChatTranscript.ModerationStatus.NOT_FLAGGED
        record.status = IndividualPipelineRecord.StageStatus.MODERATION_PASSED
    record.save()
    user_chat_transcript.save()
    logger.info(f"Individual moderation pipeline complete for participant {record.user.id}, run_id {record.run_id}")


def individual_process(record: IndividualPipelineRecord):
    """
    Stage 3: Process data via an LLM call.
    """
    # Load chat history and instructions from the database
    if record.is_for_group_direct_messaging:
        chat_history, message = load_individual_and_group_chat_history_for_direct_messaging(record.user)
        instructions = load_instruction_prompt_for_direct_messaging(record.user)
    else:
        chat_history, message = load_individual_chat_history(record.user)
        instructions = load_instruction_prompt(record.user)

    start_timer = timezone.now()
    gpt_model = record.user.gpt_model or settings.OPENAI_MODEL
    response, prompt_tokens, completion_tokens = generate_response(chat_history, instructions, message, gpt_model)
    # Strip metadata from the response if the user is not a test user
    # for testing llm responses, we want to see the raw response
    if not record.user.is_test:
        response = strip_meta(response, record.user.school_mascot)
    record.prompt_tokens = prompt_tokens
    record.completion_tokens = completion_tokens
    record.gpt_model = gpt_model
    record.processed_message = message
    record.latency = timezone.now() - start_timer
    record.instruction_prompt = instructions
    record.chat_history = format_chat_history(chat_history)
    record.response = response
    record.status = IndividualPipelineRecord.StageStatus.PROCESS_PASSED
    record.save()
    logger.info(f"Individual process pipeline complete for participant {record.user.id}, run_id {record.run_id}")


def individual_validate(record: IndividualPipelineRecord):
    """
    Stage 4: Validate the outgoing response before sending.
    """
    record.validated_message = ensure_within_character_limit(record)
    record.status = IndividualPipelineRecord.StageStatus.VALIDATE_PASSED
    record.save()
    logger.info(f"Individual validate pipeline complete for participant {record.user.id}, run_id {record.run_id}")


def individual_save_and_send(record: IndividualPipelineRecord, session: IndividualSession):
    """
    Stage 5: Retrieve the most recent response and send it to the participant.
    """
    participant_id = record.user.id
    response = record.validated_message
    # save the assistant response to the database
    assistant_chat_transcript = save_assistant_response(record, session)
    record.transcript = assistant_chat_transcript
    # Send the message via the external endpoint
    if not record.user.is_test and response:
        # TODO: revert after load testing, do not merge to test or prod
        # send_message_to_participant(participant_id, response)
        # Update the pipeline record for the sending stage
        record.status = IndividualPipelineRecord.StageStatus.SEND_PASSED
    record.save()
    logger.info(f"Individual send pipeline complete for participant {participant_id}, run_id {record.run_id}")


# =============================================================================
# Celery Tasks: Tie the Stages Together
# =============================================================================


@shared_task
def handle_inbound_individual_initial_message(group_id: str, data: dict):
    serializer = IndividualIncomingMessageSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    group_incoming_initial_message: IndividualIncomingMessage = serializer.validated_data
    ingest_initial_message(group_id, group_incoming_initial_message)


@shared_task
def individual_pipeline(participant_id: str, data: IndividualIncomingMessage):
    record: IndividualPipelineRecord | None = None
    serializer = IndividualIncomingMessageSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    individual_incoming_message: IndividualIncomingMessage = serializer.validated_data
    try:
        # Stage 1: Ingest the data and create a run record.
        record, session, user_chat_transcript = individual_ingest(participant_id, individual_incoming_message)
        assert record  # to appease the typechecker

        # Stage 2: Moderate the incoming message.
        # note that we moderate even if we got newer message since this message
        individual_moderation(record, user_chat_transcript)
        if record.status == IndividualPipelineRecord.StageStatus.MODERATION_BLOCKED:
            # if blocked, we tell BCFG and stop here
            if not record.user.is_test:
                send_moderation_message(record.user.id)
            return

        # Stage 3: Process via LLM called.
        if _newer_user_messages_exist(record):
            return
        individual_process(record)

        # Stage 4: Validate the outgoing response.
        if _newer_user_messages_exist(record):
            return
        individual_validate(record)

        # Stage 5: Send the response if the participant is not a test user.
        if _newer_user_messages_exist(record):
            return
        individual_save_and_send(record, session)
    except Exception as exc:
        if record:
            record.status = IndividualPipelineRecord.StageStatus.FAILED
            record.error_log = str(exc)
            record.save()
        logger.exception(f"Individual pipeline failed for participant {participant_id}")
        raise
