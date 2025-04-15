# group_pipeline.py
import logging
from celery import shared_task

from chat.services.group_crud import ingest_request

# from .individual_crud import save_chat_round_group
# from .arbitrar import process_arbitrar_layer, send_multiple_responses
from ..models import GroupChatTranscript, GroupPipelineRecord, GroupSession

logger = logging.getLogger(__name__)

# =============================================================================
# Pipeline Functions
# =============================================================================


def _ingest(group_id: str, data: dict) -> tuple[GroupPipelineRecord, GroupSession, GroupChatTranscript]:
    """
    Stage 1: Validate and store incoming data, then create a new run record.
    """
    group, session, user_chat_transcript = ingest_request(group_id, data)
    record = GroupPipelineRecord.objects.create(
        user=user_chat_transcript.sender,
        group=group,
        message=data.get("message", ""),
        status=GroupPipelineRecord.StageStatus.INGEST_PASSED,
    )
    logger.info(f"Group ingest pipeline complete for group {group_id}, run_id {record.run_id}")
    return record, session, user_chat_transcript


# def group_process_pipeline(run_id):
#     """
#     Stage 2: Process group chat data via strategy evaluation.
#     """
#     try:
#         record = GroupPipelineRecord.objects.get(run_id=run_id)
#         group_id = record.group.id

#         # Evaluate strategies (using your arbitrar layer) to generate responses.
#         strategy_responses = process_arbitrar_layer(group_id)
#         responses_to_send = []
#         # Save each generated strategy response into the group transcript.
#         for _, response in strategy_responses.items():
#             save_chat_round_group(group_id, None, "", response)
#             responses_to_send.append(response)

#         record.processed = True
#         record.save()
#         logger.info(f"Group process pipeline complete for group {group_id}, run_id {run_id}")
#         return responses_to_send
#     except Exception as e:
#         logger.error(f"Group process pipeline failed for run_id {run_id}: {e}")
#         record = GroupPipelineRecord.objects.get(run_id=run_id)
#         record.failed = True
#         record.error_log = str(e)
#         record.save()
#         raise


# def group_send_pipeline(run_id, responses):
#     """
#     Stage 3: Retrieve stored strategy responses and send them to the group.
#     """
#     try:
#         record = GroupPipelineRecord.objects.get(run_id=run_id)
#         group_id = record.group.id

#         # Send each generated response to the group asynchronously.
#         asyncio.run(send_multiple_responses(group_id, responses))

#         record.sent = True
#         record.save()
#         logger.info(f"Group send pipeline complete for group {group_id}, run_id {run_id}")
#     except Exception as e:
#         logger.error(f"Group send pipeline failed for run_id {run_id}: {e}")
#         record = GroupPipelineRecord.objects.get(run_id=run_id)
#         record.failed = True
#         record.error_log = str(e)
#         record.save()
#         raise


# # =============================================================================
# # Celery Tasks: Tie the Stages Together
# # =============================================================================


# # In group_pipeline.py (or a separate tasks file)
# @shared_task(bind=True, max_retries=3)
# def group_pipeline_ingest_task(self, group_id, data):
#     try:
#         run_id = group_ingest_pipeline(group_id, data)
#         # Trigger processing stage.
#         group_pipeline_process_task.delay(run_id)
#     except Exception as exc:
#         logger.error(f"Group pipeline ingestion failed for group {group_id}: {exc}")
#         raise self.retry(exc=exc, countdown=10) from exc


# @shared_task(bind=True, max_retries=3)
# def group_pipeline_process_task(self, run_id):
#     try:
#         responses = group_process_pipeline(run_id)
#         # After processing, trigger sending stage.
#         record = GroupPipelineRecord.objects.get(run_id=run_id)
#         if not record.group.is_test:
#             group_pipeline_send_task.delay(run_id, responses)
#     except Exception as exc:
#         logger.error(f"Group pipeline processing failed for run_id {run_id}: {exc}")
#         raise self.retry(exc=exc, countdown=10) from exc


# @shared_task(bind=True, max_retries=3)
# def group_pipeline_send_task(self, run_id, responses):
#     try:
#         group_send_pipeline(run_id, responses)
#     except Exception as exc:
#         logger.error(f"Group pipeline sending failed for run_id {run_id}: {exc}")
#         raise self.retry(exc=exc, countdown=10) from exc


# =============================================================================
# Celery Tasks: Tie the Stages Together
# =============================================================================


@shared_task
def group_pipeline(group_id: str, data: dict):
    record: GroupPipelineRecord | None = None
    try:
        record, session, user_chat_transcript = _ingest(group_id, data)
        # TODO Start wait and check logic per phase, including add field to keep track of phases
    except Exception as exc:
        if record:
            record.status = GroupPipelineRecord.StageStatus.FAILED
            record.error_log = str(exc)
            record.save()
        logger.exception(f"Group pipeline failed for group {group_id}")
        raise
