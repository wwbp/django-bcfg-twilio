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
    Stage 1: Validate and store incoming data, then create a new run record.
    """
    try:
        # Validate and store incoming data
        validate_ingest_individual_request(participant_id, data)

        # Create a new record with a unique run_id
        record = IndividualPipelineRecord.objects.create(
            participant_id=participant_id,
            ingested=True,
            failed=False,
            error_log=''
        )
        logger.info(
            f"Individual ingest pipeline complete for participant {participant_id}, run_id {record.run_id}"
        )
        return record.run_id
    except Exception as e:
        logger.error(
            f"Individual ingest pipeline failed for {participant_id}: {e}")
        # Create a record with the error flag if needed
        record = IndividualPipelineRecord.objects.create(
            participant_id=participant_id,
            failed=True,
            error_log=str(e)
        )
        record.save()
        raise


def individual_process_pipeline(run_id):
    """
    Stage 2: Process data via an LLM call.
    """
    try:
        record = IndividualPipelineRecord.objects.get(run_id=run_id)
        participant_id = record.participant_id

        # Load chat history and instructions from the database
        chat_history, message = load_individual_chat_history(participant_id)
        instructions = load_instruction_prompt(participant_id)

        # Generate a response using the LLM
        response = asyncio.run(generate_response(
            chat_history, instructions, message))

        # Save the generated response to the database
        save_assistant_response(participant_id, response)

        # Update the pipeline record for the processing stage
        record.processed = True
        record.save()
        logger.info(
            f"Individual process pipeline complete for participant {participant_id}, run_id {run_id}"
        )
    except Exception as e:
        logger.error(
            f"Individual process pipeline failed for run_id {run_id}: {e}"
        )
        record = IndividualPipelineRecord.objects.get(run_id=run_id)
        record.failed = True
        record.error_log = str(e)
        record.save()
        raise


def individual_send_pipeline(run_id):
    """
    Stage 3: Retrieve the most recent response and send it to the participant.
    """
    try:
        record = IndividualPipelineRecord.objects.get(run_id=run_id)
        participant_id = record.participant_id

        # Retrieve the most recent assistant response
        response = get_latest_assistant_response(participant_id)

        # Send the message via the external endpoint
        asyncio.run(
            send_message_to_participant(participant_id, response))
        # Update the pipeline record for the sending stage
        record.sent = True
        record.save()
        logger.info(
            f"Individual send pipeline complete for participant {participant_id}, run_id {run_id}"
        )
    except Exception as e:
        logger.error(
            f"Individual send pipeline failed for run_id {run_id}: {e}"
        )
        record = IndividualPipelineRecord.objects.get(run_id=run_id)
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
        run_id = individual_ingest_pipeline(participant_id, data)
        # Trigger the next stage: processing
        individual_pipeline_process_task.delay(run_id)
    except Exception as exc:
        logger.error(
            f"Individual pipeline ingestion failed for {participant_id}: {exc}"
        )
        raise self.retry(exc=exc, countdown=10)


@shared_task(bind=True, max_retries=3)
def individual_pipeline_process_task(self, run_id):
    try:
        individual_process_pipeline(run_id)
        record = IndividualPipelineRecord.objects.get(run_id=run_id)
        # Use participant_id from the record to check test user status
        if not is_test_user(record.participant_id):
            individual_pipeline_send_task.delay(run_id)
    except Exception as exc:
        logger.error(
            f"Individual pipeline processing failed for run_id {run_id}: {exc}"
        )
        raise self.retry(exc=exc, countdown=10)


@shared_task(bind=True, max_retries=3)
def individual_pipeline_send_task(self, run_id):
    try:
        individual_send_pipeline(run_id)
    except Exception as exc:
        logger.error(
            f"Individual pipeline sending failed for run_id {run_id}: {exc}"
        )
        raise self.retry(exc=exc, countdown=10)
