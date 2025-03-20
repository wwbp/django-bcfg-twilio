from asgiref.sync import async_to_sync
import asyncio
import logging
from celery import shared_task
from .moderation import moderate_message
from .crud import get_moderation_message, is_test_user, load_individual_chat_history, load_instruction_prompt, ingest_individual_request, save_assistant_response
from .completion import ensure_320_character_limit, generate_response
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
        ingest_individual_request(participant_id, data)

        # Create a new record with a unique run_id
        record = IndividualPipelineRecord.objects.create(
            participant_id=participant_id,
            ingested=True,
            message=data.get('message', ''),
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


def individual_moderation_pipeline(run_id):
    """
    Stage 2: Moderate the incoming message before processing.
    """
    try:
        record = IndividualPipelineRecord.objects.get(run_id=run_id)
        message = record.message
        blocked_str = moderate_message(message)
        if blocked_str:
            moderation_message = get_moderation_message()
            record.moderated = True
            record.response = moderation_message
        else:
            record.moderated = False
        record.save()
        logger.info(
            f"Individual moderation pipeline complete for participant {record.participant_id}, run_id {run_id}"
        )
    except Exception as e:
        logger.error(
            f"Individual moderation pipeline failed for run_id {run_id}: {e}"
        )
        record = IndividualPipelineRecord.objects.get(run_id=run_id)
        record.failed = True
        record.error_log = str(e)
        record.save()
        raise


def individual_process_pipeline(run_id):
    """
    Stage 3: Process data via an LLM call.
    """
    try:
        record = IndividualPipelineRecord.objects.get(run_id=run_id)
        participant_id = record.participant_id

        # Load chat history and instructions from the database
        chat_history, message = load_individual_chat_history(participant_id)

        # ensure the message is latest
        if message.strip() != record.message.strip():
            record.processed = False
        else:
            instructions = load_instruction_prompt(participant_id)
            response = asyncio.run(generate_response(
                chat_history, instructions, message))

            # Update the pipeline record for the processing stage
            record.instruction_prompt = instructions
            record.response = response
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


def individual_validate_pipeline(run_id):
    """
    Stage 4: Validate the outgoing response before sending.
    """
    try:
        record = IndividualPipelineRecord.objects.get(run_id=run_id)
        response = record.response
        if len(response) <= 320:
            record.shortened = False
            record.validated_message = response
        else:
            processed_response = async_to_sync(
                ensure_320_character_limit)(response)
            record.shortened = True
            record.validated_message = processed_response
        record.save()
        # Save the generated response to the database
        save_assistant_response(record.participant_id,
                                record.validated_message)
        logger.info(
            f"Individual validate pipeline complete for participant {record.participant_id}, run_id {run_id}"
        )
    except Exception as e:
        logger.error(
            f"Individual validate pipeline failed for run_id {run_id}: {e}"
        )
        record = IndividualPipelineRecord.objects.get(run_id=run_id)
        record.failed = True
        record.error_log = str(e)
        record.save()
        raise


def individual_send_pipeline(run_id):
    """
    Stage 5: Retrieve the most recent response and send it to the participant.
    """
    try:
        record = IndividualPipelineRecord.objects.get(run_id=run_id)
        participant_id = record.participant_id

        response = record.validated_message

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
        individual_pipeline_moderation_task.delay(run_id)
    except Exception as exc:
        logger.error(
            f"Individual pipeline ingestion failed for {participant_id}: {exc}"
        )
        raise self.retry(exc=exc, countdown=10)


@shared_task(bind=True, max_retries=3)
def individual_pipeline_moderation_task(self, run_id):
    try:
        individual_moderation_pipeline(run_id)
        record = IndividualPipelineRecord.objects.get(run_id=run_id)
        # Trigger the send if moderated otherwise process
        if record.moderated:
            individual_pipeline_validate_task.delay(run_id)
        else:
            individual_pipeline_process_task.delay(run_id)
    except Exception as exc:
        logger.error(
            f"Individual pipeline moderation failed for run_id {run_id}: {exc}"
        )
        raise self.retry(exc=exc, countdown=10)


@shared_task(bind=True, max_retries=3)
def individual_pipeline_process_task(self, run_id):
    try:
        individual_process_pipeline(run_id)
        record = IndividualPipelineRecord.objects.get(run_id=run_id)
        if record.processed:
            individual_pipeline_validate_task.delay(run_id)
    except Exception as exc:
        logger.error(
            f"Individual pipeline processing failed for run_id {run_id}: {exc}"
        )
        raise self.retry(exc=exc, countdown=10)


@shared_task(bind=True, max_retries=3)
def individual_pipeline_validate_task(self, run_id):
    try:
        individual_validate_pipeline(run_id)
        record = IndividualPipelineRecord.objects.get(run_id=run_id)
        if not is_test_user(record.participant_id):
            individual_pipeline_send_task.delay(run_id)
    except Exception as exc:
        logger.error(
            f"Individual pipeline validation failed for {run_id}: {exc}"
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
