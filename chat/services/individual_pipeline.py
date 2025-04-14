import logging
from celery import shared_task
from .moderation import moderate_message
from .crud import (
    load_individual_chat_history,
    load_instruction_prompt,
    ingest_request,
    save_assistant_response,
)
from .completion import MAX_RESPONSE_CHARACTER_LENGTH, ensure_within_character_limit, generate_response
from .send import individual_send_moderation, send_message_to_participant
from ..models import ChatTranscript, IndividualPipelineRecord, IndividualSession

logger = logging.getLogger(__name__)

# =============================================================================
# Pipeline Functions
# =============================================================================


def individual_ingest(participant_id: str, data: dict):
    """
    Stage 1: Validate and store incoming data, then create a new run record.
    """
    user, session, user_chat_transcript = ingest_request(participant_id, data)
    record = IndividualPipelineRecord.objects.create(
        user=user, message=data.get("message", ""), status=IndividualPipelineRecord.StageStatus.INGEST_PASSED
    )
    logger.info(f"Individual ingest pipeline complete for participant {participant_id}, run_id {record.run_id}")
    return record, session, user_chat_transcript


def individual_moderation(record: IndividualPipelineRecord, user_chat_transcript: ChatTranscript):
    """
    Stage 2: Moderate the incoming message before processing.
    """
    message = record.message
    blocked_str = moderate_message(message)
    if blocked_str:
        user_chat_transcript.moderation_status = ChatTranscript.ModerationStatus.Flagged
        record.status = IndividualPipelineRecord.StageStatus.MODERATION_BLOCKED
    else:
        user_chat_transcript.moderation_status = ChatTranscript.ModerationStatus.NotFlagged
        record.status = IndividualPipelineRecord.StageStatus.MODERATION_PASSED
    record.save()
    user_chat_transcript.save()
    logger.info(f"Individual moderation pipeline complete for participant {record.user.id}, run_id {record.run_id}")


def individual_process(record: IndividualPipelineRecord):
    """
    Stage 3: Process data via an LLM call.
    """
    # Load chat history and instructions from the database
    chat_history, message = load_individual_chat_history(record.user)

    # ensure the message is latest
    if record != IndividualPipelineRecord.objects.order_by("-created_at").first():
        record.status = IndividualPipelineRecord.StageStatus.PROCESS_SKIPPED
    else:
        instructions = load_instruction_prompt(record.user)
        response = generate_response(chat_history, instructions, message)
        record.instruction_prompt = instructions
        record.response = response
        record.status = IndividualPipelineRecord.StageStatus.PROCESS_PASSED
    record.save()
    logger.info(f"Individual process pipeline complete for participant {record.user.id}, run_id {record.run_id}")


def individual_validate(record: IndividualPipelineRecord):
    """
    Stage 4: Validate the outgoing response before sending.
    """
    response = record.response
    if len(response) <= MAX_RESPONSE_CHARACTER_LENGTH:
        record.validated_message = response
    else:
        processed_response = ensure_within_character_limit(response)
        record.validated_message = processed_response
    record.status = IndividualPipelineRecord.StageStatus.VALIDATE_PASSED
    record.save()
    logger.info(f"Individual validate pipeline complete for participant {record.user.id}, run_id {record.run_id}")


def individual_send(record: IndividualPipelineRecord, session: IndividualSession):
    """
    Stage 5: Retrieve the most recent response and send it to the participant.
    """
    participant_id = record.user.id
    response = record.validated_message
    # save the assistant response to the database
    save_assistant_response(record.user, record.validated_message, session)
    # Send the message via the external endpoint
    if not record.user.is_test:
        send_message_to_participant(participant_id, response)
        # Update the pipeline record for the sending stage
        record.status = IndividualPipelineRecord.StageStatus.SEND_PASSED
    record.save()
    logger.info(f"Individual send pipeline complete for participant {participant_id}, run_id {record.run_id}")


# =============================================================================
# Celery Tasks: Tie the Stages Together
# =============================================================================


@shared_task
def individual_pipeline(participant_id: str, data: dict):
    record: IndividualPipelineRecord | None = None
    try:
        # Stage 1: Ingest the data and create a run record.
        record, session, user_chat_transcript = individual_ingest(participant_id, data)

        # Stage 2: Moderate the incoming message.
        individual_moderation(record, user_chat_transcript)

        # Stage 3: Process via LLM call if the message was not blocked.
        if record.status == IndividualPipelineRecord.StageStatus.MODERATION_BLOCKED:
            if not record.user.is_test:
                individual_send_moderation(record.user.id)
            return

        individual_process(record)

        # Skip this run message not latest
        if record.status == IndividualPipelineRecord.StageStatus.PROCESS_SKIPPED:
            return

        # Stage 4: Validate the outgoing response.
        individual_validate(record)

        # Stage 5: Send the response if the participant is not a test user.
        individual_send(record, session)
    except Exception as exc:
        if record:
            record.status = IndividualPipelineRecord.StageStatus.FAILED
            record.error_log = str(exc)
            record.save()
        logger.exception(f"Individual pipeline failed for participant {participant_id}")
        raise
