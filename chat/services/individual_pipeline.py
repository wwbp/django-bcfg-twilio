import asyncio
import logging
from celery import shared_task
from .moderation import moderate_message
from .crud import (
    get_moderation_message,
    is_test_user,
    load_individual_chat_history,
    load_instruction_prompt,
    ingest_request,
    save_assistant_response,
)
from .completion import MAX_RESPONSE_CHARACTER_LENGTH, ensure_within_character_limit, generate_response
from .send import send_message_to_participant
from ..models import IndividualPipelineRecord, IndividualPipelineStage

logger = logging.getLogger(__name__)

# =============================================================================
# Pipeline Functions
# =============================================================================


def individual_ingest(participant_id: str, data: dict):
    """
    Stage 1: Validate and store incoming data, then create a new run record.
    """
    record = IndividualPipelineRecord.objects.create(
        participant_id=participant_id, message=data.get("message", ""), error_log=""
    )
    try:
        ingest_request(participant_id, data)
        record.stages.append(IndividualPipelineStage.INGEST_PASSED)
        record.save()
        logger.info(f"Individual ingest pipeline complete for participant {participant_id}, run_id {record.run_id}")
        return record
    except Exception as e:
        record.error_log = str(e)
        record.stages.append(IndividualPipelineStage.INGEST_FAILED)
        record.save()
        logger.error(f"Individual ingest pipeline failed for {participant_id}: {e}")
        raise


def individual_moderation(record: IndividualPipelineRecord):
    """
    Stage 2: Moderate the incoming message before processing.
    """
    message = record.message
    try:
        blocked_str = moderate_message(message)
        if blocked_str:
            moderation_message = get_moderation_message()
            record.response = moderation_message
            record.stages.append(IndividualPipelineStage.MODERATION_BLOCKED)
        else:
            record.stages.append(IndividualPipelineStage.MODERATION_PASSED)
        record.save()
        logger.info(f"Individual moderation pipeline complete for participant {record.participant_id}, run_id {record.run_id}")
    except Exception as e:
        logger.error(f"Individual moderation pipeline failed for run_id {record.run_id}: {e}")
        record.stages.append(IndividualPipelineStage.MODERATION_FAILED)
        record.error_log = str(e)
        record.save()
        raise


def individual_process(record: IndividualPipelineRecord):
    """
    Stage 3: Process data via an LLM call.
    """
    participant_id = record.participant_id
    try:
        # Load chat history and instructions from the database
        chat_history, message = load_individual_chat_history(participant_id)

        # ensure the message is latest
        # todo broken https://dev.azure.com/pod-consulting/AI%20Chatbot%20Application/_workitems/edit/9959
        if message.strip() != record.message.strip():
            record.stages.append(IndividualPipelineStage.PROCESS_SKIPPED)
            record.error_log = "Message is not the latest in chat history."
        else:
            instructions = load_instruction_prompt(participant_id)
            response = generate_response(chat_history, instructions, message)
            record.instruction_prompt = instructions
            record.response = response
            record.stages.append(IndividualPipelineStage.PROCESS_PASSED)
        record.save()
        logger.info(f"Individual process pipeline complete for participant {participant_id}, run_id {record.run_id}")
    except Exception as e:
        logger.error(f"Individual process pipeline failed for run_id {record.run_id}: {e}")
        record.error_log = str(e)
        record.stages.append(IndividualPipelineStage.PROCESS_FAILED)
        record.save()
        raise


def individual_validate(record: IndividualPipelineRecord):
    """
    Stage 4: Validate the outgoing response before sending.
    """
    response = record.response
    try:
        if len(response) <= MAX_RESPONSE_CHARACTER_LENGTH:
            record.validated_message = response
            record.stages.append(IndividualPipelineStage.VALIDATE_PASSED)
        else:
            processed_response = ensure_within_character_limit(response)
            record.validated_message = processed_response
            record.stages.append(IndividualPipelineStage.VALIDATE_CHARACTER_LIMIT_HIT)
        record.save()
        # Save the generated response to the database
        # todo move outside validation better be in send
        save_assistant_response(record.participant_id, record.validated_message)
        logger.info(f"Individual validate pipeline complete for participant {record.participant_id}, run_id {record.run_id}")
    except Exception as e:
        logger.error(f"Individual validate pipeline failed for run_id {record.run_id}: {e}")
        record.error_log = str(e)
        record.stages.append(IndividualPipelineStage.VALIDATE_FAILED)
        record.save()
        raise


def individual_send(record: IndividualPipelineRecord):
    """
    Stage 5: Retrieve the most recent response and send it to the participant.
    """
    participant_id = record.participant_id
    response = record.validated_message
    try:
        # Send the message via the external endpoint
        asyncio.run(send_message_to_participant(participant_id, response))
        # Update the pipeline record for the sending stage
        record.stages.append(IndividualPipelineStage.SEND_PASSED)
        record.save()
        logger.info(f"Individual send pipeline complete for participant {participant_id}, run_id {record.run_id}")
    except Exception as e:
        logger.error(f"Individual send pipeline failed for run_id {record.run_id}: {e}")
        record.stages.append(IndividualPipelineStage.SEND_FAILED)
        record.error_log = str(e)
        record.save()
        raise


# =============================================================================
# Celery Tasks: Tie the Stages Together
# =============================================================================


@shared_task(bind=True, max_retries=3)
def individual_pipeline(self, participant_id, data):
    try:
        # Stage 1: Ingest the data and create a run record.
        record = individual_ingest(participant_id, data)

        # Stage 2: Moderate the incoming message.
        individual_moderation(record)

        # Stage 3: Process via LLM call if the message was not blocked.
        if IndividualPipelineStage.MODERATION_PASSED in record.stages:
            individual_process(record)
        if IndividualPipelineStage.PROCESS_SKIPPED in record.stages:
            return

        # Stage 4: Validate the outgoing response.
        individual_validate(record)

        # Stage 5: Send the response if the participant is not a test user.
        if not is_test_user(record.participant_id):
            individual_send(record)
    except Exception as exc:
        logger.exception(f"Individual pipeline failed for participant {participant_id}: {exc}")
        raise self.retry(exc=exc, countdown=10) from exc
