from unittest.mock import patch
from datetime import timedelta
from django.utils import timezone

from chat.models import IndividualPipelineRecord, IndividualPipelineStage
from chat.services.individual_pipeline import individual_process


def test_individual_process_sequence():
    now = timezone.now()
    # Record 1: first message (older timestamp)
    record1 = IndividualPipelineRecord.objects.create(
        participant_id="test_user",
        message="first message",
    )
    record1.created_at = now - timedelta(seconds=10)
    record1.save(update_fields=["created_at"])

    # Record 2: second message (latest timestamp)
    record2 = IndividualPipelineRecord.objects.create(
        participant_id="test_user",
        message="second message",
    )
    record2.created_at = now
    record2.save(update_fields=["created_at"])

    # --- Call individual_process on each record ---
    # Process the first record: since it's not the latest, skip
    with (
        patch("chat.services.individual_pipeline.generate_response", return_value=["LLM response"]) as mock_gen,
    ):
        individual_process(record1)
        record1.refresh_from_db()
        assert IndividualPipelineStage.PROCESS_SKIPPED in record1.stages, (
            "Expected PROCESS_SKIPPED for the first (non-latest) record."
        )

        # Process the second record: since it is the latest, process
        individual_process(record2)
        record2.refresh_from_db()
        assert IndividualPipelineStage.PROCESS_PASSED in record2.stages, (
            "Expected PROCESS_PASSED for the latest record2."
        )
