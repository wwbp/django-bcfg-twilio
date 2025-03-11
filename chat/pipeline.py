import asyncio
import logging
from celery import shared_task
from .crud import get_latest_assistant_response, is_test_user, load_individual_chat_history, load_instruction_prompt, save_assistant_response, validate_ingest_individual_request
from .completion import generate_response
from .send import send_message_to_participant
from .models import IndividualPipelineRecord

logger = logging.getLogger(__name__)

# =============================================================================
# Pipeline Functions
# =============================================================================


def individual_ingest_pipeline(participant_id: str, data: dict):
    """
    Stage 1: Validate and store incoming data, then update the pipeline record.
    """
    try:
        # Validate and store incoming data
        validate_ingest_individual_request(participant_id, data)

        # Create or update the pipeline record for ingestion stage
        IndividualPipelineRecord.objects.update_or_create(
            participant_id=participant_id,
            defaults={'ingested': True, 'failed': False, 'error_log': ''}
        )
        logger.info(
            f"Individual ingest pipeline complete for participant {participant_id}")
    except Exception as e:
        logger.error(
            f"Individual ingest pipeline failed for {participant_id}: {e}")
        record, _ = IndividualPipelineRecord.objects.update_or_create(
            participant_id=participant_id
        )
        record.failed = True
        record.error_log = str(e)
        record.save()
        raise


def individual_process_pipeline(participant_id: str):
    """
    Stage 2: Process data via an LLM call.
    """
    try:
        # Load chat history and instructions from the database
        chat_history, message = load_individual_chat_history(participant_id)
        instructions = load_instruction_prompt(participant_id)

        # Generate a response using the LLM
        response = asyncio.run(generate_response(
            chat_history, instructions, message))

        # Save the generated response to the database
        save_assistant_response(participant_id, response)

        # Update the pipeline record for processing stage
        record = IndividualPipelineRecord.objects.get(
            participant_id=participant_id)
        record.processed = True
        record.save()
        logger.info(
            f"Individual process pipeline complete for participant {participant_id}")
    except Exception as e:
        logger.error(
            f"Individual process pipeline failed for {participant_id}: {e}")
        record = IndividualPipelineRecord.objects.get(
            participant_id=participant_id)
        record.failed = True
        record.error_log = str(e)
        record.save()
        raise


def individual_send_pipeline(participant_id: str):
    """
    Stage 3: Retrieve the most recent response and send it to the participant.
    """
    try:
        # todo: need to get latest response form db transcript
        response = get_latest_assistant_response(participant_id)

        # Send the message via the external endpoint
        asyncio.run(
            send_message_to_participant(participant_id, response))
        # Update the pipeline record for sending stage
        record = IndividualPipelineRecord.objects.get(
            participant_id=participant_id)
        record.sent = True
        record.save()
        logger.info(
            f"Individual send pipeline complete for participant {participant_id}")
    except Exception as e:
        logger.error(
            f"Individual send pipeline failed for {participant_id}: {e}")
        record = IndividualPipelineRecord.objects.get(
            participant_id=participant_id)
        record.failed = True
        record.error_log = str(e)
        record.save()
        raise

# =============================================================================
# Celery Tasks: Tie the Stages Together
# =============================================================================


@shared_task(bind=True, max_retries=3)
def individual_pipeline_ingest_task(self, participant_id, data):
    try:
        individual_ingest_pipeline(participant_id, data)
        # Trigger the next stage: processing
        individual_pipeline_process_task.delay(participant_id)
    except Exception as exc:
        logger.error(
            f"Individual pipeline ingestion failed for {participant_id}: {exc}")
        raise self.retry(exc=exc, countdown=10)


@shared_task(bind=True, max_retries=3)
def individual_pipeline_process_task(self, participant_id):
    try:
        individual_process_pipeline(participant_id)
        # Trigger the next stage: sending
        if not is_test_user(participant_id):
            individual_pipeline_send_task.delay(participant_id)
    except Exception as exc:
        logger.error(
            f"Individual pipeline processing failed for {participant_id}: {exc}")
        raise self.retry(exc=exc, countdown=10)


@shared_task(bind=True, max_retries=3)
def individual_pipeline_send_task(self, participant_id):
    try:
        individual_send_pipeline(participant_id)
    except Exception as exc:
        logger.error(
            f"Individual pipeline sending failed for {participant_id}: {exc}")
        raise self.retry(exc=exc, countdown=10)
