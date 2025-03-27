import pytest
from chat.models import IndividualPipelineRecord
from chat.services.individual_pipeline import (
    individual_ingest_pipeline,
    individual_moderation_pipeline,
    individual_process_pipeline,
    individual_validate_pipeline,
    individual_send_pipeline,
    individual_pipeline_task,
)
from chat.services.completion import MAX_RESPONSE_CHARACTER_LENGTH


# -----------------------------------------------------------------------------
# Dummy Functions for Dependency Simulation
# -----------------------------------------------------------------------------
def dummy_ingest(participant_id, data):
    # Assume data is valid; do nothing
    return None


def dummy_moderate(message):
    # Simulate no blocking; return an empty string.
    return ""


def dummy_moderate_block(message):
    # Simulate message blocking by moderation.
    return "block"


def dummy_get_moderation_message():
    return "moderation response"


def dummy_load_chat_history(participant_id):
    # Return empty history and a message that exactly matches the record.
    return ([], "Test Message")


def dummy_load_chat_history_mismatch(participant_id):
    # Return history with a latest message that doesn't match the record.
    return ([], "Different Message")


def dummy_load_instruction_prompt(participant_id):
    return "dummy instructions"


def dummy_generate_response(history, instructions, message):
    return "LLM response"


def dummy_ensure_within_character_limit(response):
    return "shortened response"


async def dummy_send_message(participant_id, message):
    return None


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------
@pytest.fixture
def valid_data():
    return {
        "context": {
            "school_name": "Test School",
            "school_mascot": "Test Mascot",
            "name": "Test User",
            "initial_message": "Test Message",
            "week_number": 1,
        },
        "message": "Test Message",
    }


@pytest.fixture
def default_pipeline_monkeypatch(monkeypatch):
    """
    Sets default monkeypatches for all dependencies in the individual pipeline.
    Tests can override specific functions as needed.
    """
    monkeypatch.setattr("chat.services.individual_pipeline.ingest_individual_request", dummy_ingest)
    monkeypatch.setattr("chat.services.individual_pipeline.moderate_message", dummy_moderate)
    monkeypatch.setattr("chat.services.individual_pipeline.load_individual_chat_history", dummy_load_chat_history)
    monkeypatch.setattr("chat.services.individual_pipeline.load_instruction_prompt", dummy_load_instruction_prompt)
    monkeypatch.setattr("chat.services.individual_pipeline.generate_response", dummy_generate_response)
    monkeypatch.setattr("chat.services.individual_pipeline.ensure_within_character_limit", lambda r: r)
    monkeypatch.setattr("chat.services.individual_pipeline.save_assistant_response", lambda pid, msg: None)
    monkeypatch.setattr("chat.services.individual_pipeline.send_message_to_participant", dummy_send_message)
    monkeypatch.setattr("chat.services.individual_pipeline.is_test_user", lambda pid: False)


def get_record(run_id):
    return IndividualPipelineRecord.objects.get(run_id=run_id)


# -----------------------------------------------------------------------------
# Stage 1: Ingestion Tests
# -----------------------------------------------------------------------------
@pytest.mark.django_db
def test_ingest_success(default_pipeline_monkeypatch, valid_data):
    participant_id = "user_ingest_success"
    run_id = individual_ingest_pipeline(participant_id, valid_data)
    record = get_record(run_id)
    assert record.participant_id == participant_id
    assert record.message == valid_data["message"]
    assert record.ingested is True
    assert record.failed is False


@pytest.mark.django_db
def test_ingest_failure(monkeypatch, valid_data):
    participant_id = "user_ingest_failure"

    def failing_ingest(pid, data):
        raise Exception("Ingestion error")

    monkeypatch.setattr("chat.services.individual_pipeline.ingest_individual_request", failing_ingest)
    with pytest.raises(Exception, match="Ingestion error"):
        individual_ingest_pipeline(participant_id, valid_data)
    record = IndividualPipelineRecord.objects.filter(participant_id=participant_id).first()
    assert record is not None
    assert record.failed is True
    assert "Ingestion error" in record.error_log


# -----------------------------------------------------------------------------
# Stage 2: Moderation Tests
# -----------------------------------------------------------------------------
@pytest.mark.django_db
def test_moderation_no_block(default_pipeline_monkeypatch, valid_data):
    participant_id = "user_mod_no_block"
    run_id = individual_ingest_pipeline(participant_id, valid_data)
    # Use the default dummy_moderate (no block)
    individual_moderation_pipeline(run_id)
    record = get_record(run_id)
    assert record.moderated is False


@pytest.mark.django_db
def test_moderation_block(default_pipeline_monkeypatch, valid_data, monkeypatch):
    participant_id = "user_mod_block"
    run_id = individual_ingest_pipeline(participant_id, valid_data)
    monkeypatch.setattr("chat.services.individual_pipeline.moderate_message", dummy_moderate_block)
    monkeypatch.setattr("chat.services.individual_pipeline.get_moderation_message", dummy_get_moderation_message)
    individual_moderation_pipeline(run_id)
    record = get_record(run_id)
    assert record.moderated is True
    assert record.response == "moderation response"


@pytest.mark.django_db
def test_moderation_exception(default_pipeline_monkeypatch, valid_data, monkeypatch):
    participant_id = "user_mod_exception"
    run_id = individual_ingest_pipeline(participant_id, valid_data)

    def failing_moderate(message):
        raise Exception("Moderation failure")

    monkeypatch.setattr("chat.services.individual_pipeline.moderate_message", failing_moderate)
    with pytest.raises(Exception, match="Moderation failure"):
        individual_moderation_pipeline(run_id)
    record = get_record(run_id)
    assert record.failed is True
    assert "Moderation failure" in record.error_log


# -----------------------------------------------------------------------------
# Stage 3: Processing Tests
# -----------------------------------------------------------------------------
@pytest.mark.django_db
def test_processing_success(default_pipeline_monkeypatch, valid_data, monkeypatch):
    participant_id = "user_process_success"
    run_id = individual_ingest_pipeline(participant_id, valid_data)
    # Use matching chat history
    monkeypatch.setattr("chat.services.individual_pipeline.load_individual_chat_history", dummy_load_chat_history)
    monkeypatch.setattr("chat.services.individual_pipeline.load_instruction_prompt", dummy_load_instruction_prompt)
    monkeypatch.setattr("chat.services.individual_pipeline.generate_response", dummy_generate_response)
    individual_process_pipeline(run_id)
    record = get_record(run_id)
    assert record.processed is True
    assert record.instruction_prompt == "dummy instructions"
    assert record.response == "LLM response"


@pytest.mark.django_db
def test_processing_message_mismatch(default_pipeline_monkeypatch, valid_data, monkeypatch):
    participant_id = "user_process_mismatch"
    run_id = individual_ingest_pipeline(participant_id, valid_data)
    monkeypatch.setattr(
        "chat.services.individual_pipeline.load_individual_chat_history", dummy_load_chat_history_mismatch
    )
    individual_process_pipeline(run_id)
    record = get_record(run_id)
    # When messages don't match, processing is skipped.
    assert record.processed is False


@pytest.mark.django_db
def test_processing_exception(default_pipeline_monkeypatch, valid_data, monkeypatch):
    participant_id = "user_process_exception"
    run_id = individual_ingest_pipeline(participant_id, valid_data)
    monkeypatch.setattr("chat.services.individual_pipeline.load_individual_chat_history", dummy_load_chat_history)
    monkeypatch.setattr("chat.services.individual_pipeline.load_instruction_prompt", dummy_load_instruction_prompt)

    def failing_generate_response(history, instructions, message):
        raise Exception("Processing error")

    monkeypatch.setattr("chat.services.individual_pipeline.generate_response", failing_generate_response)
    with pytest.raises(Exception, match="Processing error"):
        individual_process_pipeline(run_id)
    record = get_record(run_id)
    assert record.failed is True
    assert "Processing error" in record.error_log


# -----------------------------------------------------------------------------
# Stage 4: Validation Tests
# -----------------------------------------------------------------------------
@pytest.mark.django_db
def test_validation_within_limit(default_pipeline_monkeypatch, valid_data, monkeypatch):
    participant_id = "user_validate_within"
    run_id = individual_ingest_pipeline(participant_id, valid_data)
    record = get_record(run_id)
    record.response = "Short response"
    record.save()
    monkeypatch.setattr("chat.services.individual_pipeline.save_assistant_response", lambda pid, msg: None)
    individual_validate_pipeline(run_id)
    record.refresh_from_db()
    assert record.validated_message == "Short response"
    assert record.shortened is False


@pytest.mark.django_db
def test_validation_exceeding_limit(default_pipeline_monkeypatch, valid_data, monkeypatch):
    participant_id = "user_validate_exceed"
    run_id = individual_ingest_pipeline(participant_id, valid_data)
    record = get_record(run_id)
    long_response = "X" * (MAX_RESPONSE_CHARACTER_LENGTH + 10)
    record.response = long_response
    record.save()
    monkeypatch.setattr(
        "chat.services.individual_pipeline.ensure_within_character_limit", dummy_ensure_within_character_limit
    )
    monkeypatch.setattr("chat.services.individual_pipeline.save_assistant_response", lambda pid, msg: None)
    individual_validate_pipeline(run_id)
    record.refresh_from_db()
    assert record.shortened is True
    assert record.validated_message == "shortened response"


@pytest.mark.django_db
def test_validation_exception(default_pipeline_monkeypatch, valid_data, monkeypatch):
    participant_id = "user_validate_exception"
    run_id = individual_ingest_pipeline(participant_id, valid_data)
    record = get_record(run_id)
    # Set a long response to force calling ensure_within_character_limit
    record.response = "X" * (MAX_RESPONSE_CHARACTER_LENGTH + 1)
    record.save()

    def failing_ensure(response):
        raise Exception("Validation error")

    monkeypatch.setattr("chat.services.individual_pipeline.ensure_within_character_limit", failing_ensure)

    with pytest.raises(Exception, match="Validation error"):
        individual_validate_pipeline(run_id)

    record.refresh_from_db()
    assert record.failed is True
    assert "Validation error" in record.error_log


# -----------------------------------------------------------------------------
# Stage 5: Sending Tests
# -----------------------------------------------------------------------------
@pytest.mark.django_db
def test_sending_success(default_pipeline_monkeypatch, valid_data, monkeypatch):
    participant_id = "user_send_success"
    run_id = individual_ingest_pipeline(participant_id, valid_data)
    record = get_record(run_id)
    record.validated_message = "Final response"
    record.save()
    monkeyatch_send = monkeypatch.setattr(
        "chat.services.individual_pipeline.send_message_to_participant", dummy_send_message
    )
    individual_send_pipeline(run_id)
    record.refresh_from_db()
    assert record.sent is True


@pytest.mark.django_db
def test_sending_exception(default_pipeline_monkeypatch, valid_data, monkeypatch):
    participant_id = "user_send_exception"
    run_id = individual_ingest_pipeline(participant_id, valid_data)
    record = get_record(run_id)
    record.validated_message = "Final response"
    record.save()

    async def failing_send(pid, message):
        raise Exception("Send error")

    monkeypatch.setattr("chat.services.individual_pipeline.send_message_to_participant", failing_send)
    with pytest.raises(Exception, match="Send error"):
        individual_send_pipeline(run_id)
    record.refresh_from_db()
    assert record.failed is True
    assert "Send error" in record.error_log


# -----------------------------------------------------------------------------
# Overall Pipeline Task Tests
# -----------------------------------------------------------------------------
@pytest.mark.django_db
def test_pipeline_task_full_success(default_pipeline_monkeypatch, valid_data, monkeypatch):
    participant_id = "user_full_success"
    # All defaults in the fixture simulate a successful run.
    individual_pipeline_task(participant_id, valid_data)
    record = IndividualPipelineRecord.objects.filter(participant_id=participant_id).order_by("-id").first()
    assert record.ingested is True
    assert record.moderated is False
    assert record.processed is True
    assert record.sent is True


@pytest.mark.django_db
def test_pipeline_task_moderated(default_pipeline_monkeypatch, valid_data, monkeypatch):
    participant_id = "user_pipeline_moderated"
    run_id = individual_ingest_pipeline(participant_id, valid_data)
    monkeypatch.setattr("chat.services.individual_pipeline.moderate_message", dummy_moderate_block)
    monkeypatch.setattr("chat.services.individual_pipeline.get_moderation_message", dummy_get_moderation_message)
    individual_moderation_pipeline(run_id)
    # For moderated messages, processing should be skipped.
    record = get_record(run_id)
    assert record.moderated is True
    # Even if processing is skipped, validation and sending run.
    monkeypatch.setattr("chat.services.individual_pipeline.send_message_to_participant", dummy_send_message)
    individual_validate_pipeline(run_id)
    individual_send_pipeline(run_id)
    record.refresh_from_db()
    assert record.sent is True


@pytest.mark.django_db
def test_pipeline_task_test_user(default_pipeline_monkeypatch, valid_data, monkeypatch):
    participant_id = "user_test_user"
    monkeypatch.setattr("chat.services.individual_pipeline.is_test_user", lambda pid: True)
    individual_pipeline_task(participant_id, valid_data)
    record = IndividualPipelineRecord.objects.filter(participant_id=participant_id).order_by("-id").first()
    # For test users, sending should be skipped.
    assert record.sent is not True


@pytest.mark.django_db
def test_pipeline_task_exception_propagation(default_pipeline_monkeypatch, valid_data, monkeypatch):
    participant_id = "user_pipeline_exception"

    def failing_generate_response(history, instructions, message):
        raise Exception("Processing exception in task")

    monkeypatch.setattr("chat.services.individual_pipeline.generate_response", failing_generate_response)
    with pytest.raises(Exception, match="Processing exception in task"):
        individual_pipeline_task(participant_id, valid_data)
    record = IndividualPipelineRecord.objects.filter(participant_id=participant_id).order_by("-id").first()
    assert record.failed is True
    assert "Processing exception in task" in record.error_log
