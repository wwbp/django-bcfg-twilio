# group_pipeline.py
import asyncio
import logging
from celery import shared_task
from .crud import validate_ingest_group_request, save_chat_round_group
from .arbitrar import process_arbitrar_layer, send_multiple_responses
from ..models import GroupPipelineRecord

logger = logging.getLogger(__name__)

# =============================================================================
# Pipeline Functions
# =============================================================================


def group_ingest_pipeline(group_id: str, data: dict):
    """
    Stage 1: Validate and store incoming group data, then create a new group run record.
    """
    try:
        # Validate and update the database with group info.
        group = validate_ingest_group_request(group_id, data)

        # Create a new pipeline record for the group.
        record = GroupPipelineRecord.objects.create(
            group=group, ingested=True, processed=False, sent=False, failed=False, error_log=""
        )
        logger.info(f"Group ingest pipeline complete for group {group_id}, run_id {record.run_id}")
        return record.run_id
    except Exception as e:
        logger.error(f"Group ingest pipeline failed for group {group_id}: {e}")
        record = GroupPipelineRecord.objects.create(group_id=group_id, failed=True, error_log=str(e))
        record.save()
        raise


def group_process_pipeline(run_id):
    """
    Stage 2: Process group chat data via strategy evaluation.
    """
    try:
        record = GroupPipelineRecord.objects.get(run_id=run_id)
        group_id = record.group.id

        # Evaluate strategies (using your arbitrar layer) to generate responses.
        strategy_responses = process_arbitrar_layer(group_id)
        responses_to_send = []
        # Save each generated strategy response into the group transcript.
        for _, response in strategy_responses.items():
            save_chat_round_group(group_id, None, "", response)
            responses_to_send.append(response)

        record.processed = True
        record.save()
        logger.info(f"Group process pipeline complete for group {group_id}, run_id {run_id}")
        return responses_to_send
    except Exception as e:
        logger.error(f"Group process pipeline failed for run_id {run_id}: {e}")
        record = GroupPipelineRecord.objects.get(run_id=run_id)
        record.failed = True
        record.error_log = str(e)
        record.save()
        raise


def group_send_pipeline(run_id, responses):
    """
    Stage 3: Retrieve stored strategy responses and send them to the group.
    """
    try:
        record = GroupPipelineRecord.objects.get(run_id=run_id)
        group_id = record.group.id

        # Send each generated response to the group asynchronously.
        asyncio.run(send_multiple_responses(group_id, responses))

        record.sent = True
        record.save()
        logger.info(f"Group send pipeline complete for group {group_id}, run_id {run_id}")
    except Exception as e:
        logger.error(f"Group send pipeline failed for run_id {run_id}: {e}")
        record = GroupPipelineRecord.objects.get(run_id=run_id)
        record.failed = True
        record.error_log = str(e)
        record.save()
        raise


# =============================================================================
# Celery Tasks: Tie the Stages Together
# =============================================================================


# In group_pipeline.py (or a separate tasks file)
@shared_task(bind=True, max_retries=3)
def group_pipeline_ingest_task(self, group_id, data):
    try:
        run_id = group_ingest_pipeline(group_id, data)
        # Trigger processing stage.
        group_pipeline_process_task.delay(run_id)
    except Exception as exc:
        logger.error(f"Group pipeline ingestion failed for group {group_id}: {exc}")
        raise self.retry(exc=exc, countdown=10) from exc


@shared_task(bind=True, max_retries=3)
def group_pipeline_process_task(self, run_id):
    try:
        responses = group_process_pipeline(run_id)
        # After processing, trigger sending stage.
        record = GroupPipelineRecord.objects.get(run_id=run_id)
        if not record.group.is_test:
            group_pipeline_send_task.delay(run_id, responses)
    except Exception as exc:
        logger.error(f"Group pipeline processing failed for run_id {run_id}: {exc}")
        raise self.retry(exc=exc, countdown=10) from exc


@shared_task(bind=True, max_retries=3)
def group_pipeline_send_task(self, run_id, responses):
    try:
        group_send_pipeline(run_id, responses)
    except Exception as exc:
        logger.error(f"Group pipeline sending failed for run_id {run_id}: {exc}")
        raise self.retry(exc=exc, countdown=10) from exc
