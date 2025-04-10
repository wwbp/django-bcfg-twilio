from unittest.mock import patch
from datetime import timedelta
from django.utils import timezone

from chat.models import Control, IndividualPipelineRecord, IndividualSession, MessageType, Prompt, User
from chat.services.individual_pipeline import individual_process


def test_individual_process_sequence():
    now = timezone.now()
    user = User.objects.create(id="test_user")
    session = IndividualSession.objects.create(
        user=user,
        initial_message="Test message",
        week_number=1,
        message_type=MessageType.INITIAL,
    )
    prompt = Prompt.objects.create(
        week=1,
        type=MessageType.INITIAL,
        activity="base activity",
    )
    control = Control.objects.create(system="System", persona="Persona")
    # Record 1: first message (older timestamp)
    record1 = IndividualPipelineRecord.objects.create(
        user=user,
        message="first message",
    )
    record1.created_at = now - timedelta(seconds=10)
    record1.save(update_fields=["created_at"])

    # Record 2: second message (latest timestamp)
    record2 = IndividualPipelineRecord.objects.create(
        user=user,
        message="second message",
    )
    record2.created_at = now
    record2.save(update_fields=["created_at"])

    # --- Call individual_process on each record ---
    with patch("chat.services.individual_pipeline.generate_response", return_value="LLM response") as mock_gen:
        # Process the first record: since it's not the latest, it should be skipped.
        individual_process(record1)
        record1.refresh_from_db()
        assert record1.status == IndividualPipelineRecord.StageStatus.PROCESS_SKIPPED, (
            "Expected PROCESS_SKIPPED for the first (non-latest) record."
        )

        # Process the second record: since it is the latest, it should be processed.
        individual_process(record2)
        record2.refresh_from_db()
        assert record2.status == IndividualPipelineRecord.StageStatus.PROCESS_PASSED, (
            "Expected PROCESS_PASSED for the latest record."
        )
