# group_pipeline.py
import json
import logging
import random
from celery import shared_task
from django_celery_beat.models import PeriodicTask, ClockedSchedule
from django.db import transaction
from django.utils import timezone

from chat.serializers import GroupIncomingMessage, GroupIncomingMessageSerializer
from chat.services.group_crud import ingest_request
from chat.services.moderation import moderate_message
from chat.services.send import send_moderation_message

from ..models import GroupChatTranscript, GroupPipelineRecord, GroupScheduledTaskAssociation

logger = logging.getLogger(__name__)

# =============================================================================
# Pipeline Functions
# =============================================================================


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
    # TODO 9853 - get this from the database
    return random.randint(60, 300)


def _clear_existing_and_schedule_response_to_group(
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
            task="chat.services.group_pipeline.respond_to_group",
            clocked=interval,
            kwargs=json.dumps({"user_chat_transcript_id": last_user_chat_transcript.id, "run_id": str(record.run_id)}),
            one_off=True,
        )
        GroupScheduledTaskAssociation.objects.create(group=record.group, task=task)
    logger.info(
        f"Scheduled response for group {record.group.id}, sender {record.user.id}, run_id {record.run_id} "
        f"after {delay_sec} seconds"
    )


# =============================================================================
# Celery Tasks: Tie the Stages Together
# =============================================================================


@shared_task
def handle_inbound_group_message(group_id: str, data: dict):
    # we reuse serializer used in inbound http endpoint, which already validated data
    serializer = GroupIncomingMessageSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    group_incoming_message: GroupIncomingMessage = serializer.validated_data

    record: GroupPipelineRecord | None = None
    try:
        record, user_chat_transcript = _ingest(group_id, group_incoming_message)
        _moderate(record, user_chat_transcript)
        if record.status == GroupPipelineRecord.StageStatus.MODERATION_BLOCKED:
            # if blocked, we tell BCFG and stop here
            if not record.group.is_test and not record.user.is_test:
                send_moderation_message(record.user.id)
            return

        if _newer_user_messages_exist(record):
            return
        _clear_existing_and_schedule_response_to_group(user_chat_transcript, record)
    except Exception as exc:
        if record:
            record.status = GroupPipelineRecord.StageStatus.FAILED
            record.error_log = str(exc)
            record.save()
        logger.exception(f"Group pipeline failed for group {group_id}")
        raise


@shared_task
def respond_to_group(run_id: str, user_chat_transcript_id: int):
    """
    Stage 3: Send the response to the group.
    """
    record = GroupPipelineRecord.objects.get(run_id=run_id)
    user_chat_transcript = GroupChatTranscript.objects.get(id=user_chat_transcript_id)
    # if _newer_user_messages_exist(record):
    #     return
    # TODO Implement sending logic here
    logger.info(
        f"Group response pipeline complete for group {record.group.id}, sender {record.user.id}, run_id {record.run_id}"
    )
