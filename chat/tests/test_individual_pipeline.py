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


def dummy_ingest(pid, data):
    return None


def dummy_moderate(msg):
    return ""


def dummy_moderate_block(msg):
    return "block"


def dummy_get_moderation_message():
    return "moderation response"


def dummy_load_chat_history(pid):
    return ([], "Test Message")


def dummy_load_chat_history_mismatch(pid):
    return ([], "Different Message")


def dummy_load_instruction_prompt(pid):
    return "dummy instructions"


def dummy_generate_response(hist, instr, msg):
    return "LLM response"


def dummy_ensure_within_character_limit(resp):
    return "shortened response"


async def dummy_send_message(pid, msg):
    return None


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
def default_monkeypatch(monkeypatch):
    monkeypatch.setattr("chat.services.individual_pipeline.ingest_individual_request", dummy_ingest)
    monkeypatch.setattr("chat.services.individual_pipeline.moderate_message", dummy_moderate)
    monkeypatch.setattr("chat.services.individual_pipeline.load_individual_chat_history", dummy_load_chat_history)
    monkeypatch.setattr("chat.services.individual_pipeline.load_instruction_prompt", dummy_load_instruction_prompt)
    monkeypatch.setattr("chat.services.individual_pipeline.generate_response", dummy_generate_response)
    monkeypatch.setattr("chat.services.individual_pipeline.ensure_within_character_limit", lambda r: r)
    monkeypatch.setattr("chat.services.individual_pipeline.save_assistant_response", lambda pid, msg: None)
    monkeypatch.setattr("chat.services.individual_pipeline.send_message_to_participant", dummy_send_message)
    monkeypatch.setattr("chat.services.individual_pipeline.is_test_user", lambda pid: False)
    return monkeypatch


def get_record(run_id):
    return IndividualPipelineRecord.objects.get(run_id=run_id)


# Ingestion Stage Tests
class TestIngestionPipeline:
    def test_ingest_success(self, default_monkeypatch, valid_data):
        """Test that ingestion creates a record correctly when data is valid."""
        pid = "user_ingest_success"
        run_id = individual_ingest_pipeline(pid, valid_data)
        record = get_record(run_id)
        assert record.participant_id == pid
        assert record.message == valid_data["message"]
        assert record.ingested and not record.failed

    def test_ingest_failure(self, monkeypatch, valid_data):
        """Test ingestion failure when an exception is thrown during request ingestion."""
        pid = "user_ingest_failure"
        monkeypatch.setattr(
            "chat.services.individual_pipeline.ingest_individual_request",
            lambda pid, data: (_ for _ in ()).throw(Exception("Ingestion error")),
        )
        with pytest.raises(Exception, match="Ingestion error"):
            individual_ingest_pipeline(pid, valid_data)
        record = IndividualPipelineRecord.objects.filter(participant_id=pid).first()
        assert record and record.failed and "Ingestion error" in record.error_log


# Moderation Stage Tests
class TestModerationPipeline:
    def test_moderation_no_block(self, default_monkeypatch, valid_data):
        """Test moderation passes with no block response."""
        pid = "user_mod_no_block"
        run_id = individual_ingest_pipeline(pid, valid_data)
        individual_moderation_pipeline(run_id)
        assert not get_record(run_id).moderated

    def test_moderation_block(self, default_monkeypatch, valid_data, monkeypatch):
        """Test that moderation marks the record and sets a moderation response when blocked."""
        pid = "user_mod_block"
        run_id = individual_ingest_pipeline(pid, valid_data)
        monkeypatch.setattr("chat.services.individual_pipeline.moderate_message", dummy_moderate_block)
        monkeypatch.setattr("chat.services.individual_pipeline.get_moderation_message", dummy_get_moderation_message)
        individual_moderation_pipeline(run_id)
        record = get_record(run_id)
        assert record.moderated and record.response == "moderation response"

    def test_moderation_exception(self, default_monkeypatch, valid_data, monkeypatch):
        """Test that an exception during moderation flags the record as failed."""
        pid = "user_mod_exception"
        run_id = individual_ingest_pipeline(pid, valid_data)
        monkeypatch.setattr(
            "chat.services.individual_pipeline.moderate_message",
            lambda msg: (_ for _ in ()).throw(Exception("Moderation failure")),
        )
        with pytest.raises(Exception, match="Moderation failure"):
            individual_moderation_pipeline(run_id)
        record = get_record(run_id)
        assert record.failed and "Moderation failure" in record.error_log


# ===============================
# Processing Stage Tests
# ===============================
class TestProcessingPipeline:
    def test_processing_success(self, default_monkeypatch, valid_data, monkeypatch):
        """Test successful processing of a valid message."""
        pid = "user_process_success"
        run_id = individual_ingest_pipeline(pid, valid_data)
        monkeypatch.setattr("chat.services.individual_pipeline.load_individual_chat_history", dummy_load_chat_history)
        monkeypatch.setattr("chat.services.individual_pipeline.load_instruction_prompt", dummy_load_instruction_prompt)
        monkeypatch.setattr("chat.services.individual_pipeline.generate_response", dummy_generate_response)
        individual_process_pipeline(run_id)
        record = get_record(run_id)
        assert record.processed
        assert record.instruction_prompt == "dummy instructions"
        assert record.response == "LLM response"

    def test_processing_message_mismatch(self, default_monkeypatch, valid_data, monkeypatch):
        """Test that processing fails when the latest message does not match the record."""
        pid = "user_process_mismatch"
        run_id = individual_ingest_pipeline(pid, valid_data)
        monkeypatch.setattr(
            "chat.services.individual_pipeline.load_individual_chat_history", dummy_load_chat_history_mismatch
        )
        individual_process_pipeline(run_id)
        assert not get_record(run_id).processed

    def test_processing_exception(self, default_monkeypatch, valid_data, monkeypatch):
        """Test that an exception during processing flags the record as failed."""
        pid = "user_process_exception"
        run_id = individual_ingest_pipeline(pid, valid_data)
        monkeypatch.setattr("chat.services.individual_pipeline.load_individual_chat_history", dummy_load_chat_history)
        monkeypatch.setattr("chat.services.individual_pipeline.load_instruction_prompt", dummy_load_instruction_prompt)
        monkeypatch.setattr(
            "chat.services.individual_pipeline.generate_response",
            lambda h, i, m: (_ for _ in ()).throw(Exception("Processing error")),
        )
        with pytest.raises(Exception, match="Processing error"):
            individual_process_pipeline(run_id)
        record = get_record(run_id)
        assert record.failed and "Processing error" in record.error_log


# ===============================
# Validation Stage Tests
# ===============================
class TestValidationPipeline:
    def test_validation_within_limit(self, default_monkeypatch, valid_data, monkeypatch):
        """Test that a response within the character limit is validated without shortening."""
        pid = "user_validate_within"
        run_id = individual_ingest_pipeline(pid, valid_data)
        record = get_record(run_id)
        record.response = "Short response"
        record.save()
        monkeypatch.setattr("chat.services.individual_pipeline.save_assistant_response", lambda pid, msg: None)
        individual_validate_pipeline(run_id)
        record.refresh_from_db()
        assert record.validated_message == "Short response"
        assert not record.shortened

    def test_validation_exceeding_limit(self, default_monkeypatch, valid_data, monkeypatch):
        """Test that a response exceeding the limit is shortened and validated."""
        pid = "user_validate_exceed"
        run_id = individual_ingest_pipeline(pid, valid_data)
        record = get_record(run_id)
        long_resp = "X" * (MAX_RESPONSE_CHARACTER_LENGTH + 10)
        record.response = long_resp
        record.save()
        monkeypatch.setattr(
            "chat.services.individual_pipeline.ensure_within_character_limit", dummy_ensure_within_character_limit
        )
        monkeypatch.setattr("chat.services.individual_pipeline.save_assistant_response", lambda pid, msg: None)
        individual_validate_pipeline(run_id)
        record.refresh_from_db()
        assert record.shortened
        assert record.validated_message == "shortened response"

    def test_validation_exception(self, default_monkeypatch, valid_data, monkeypatch):
        """Test that an exception during validation flags the record as failed."""
        pid = "user_validate_exception"
        run_id = individual_ingest_pipeline(pid, valid_data)
        record = get_record(run_id)
        record.response = "X" * (MAX_RESPONSE_CHARACTER_LENGTH + 1)
        record.save()
        monkeypatch.setattr(
            "chat.services.individual_pipeline.ensure_within_character_limit",
            lambda r: (_ for _ in ()).throw(Exception("Validation error")),
        )
        with pytest.raises(Exception, match="Validation error"):
            individual_validate_pipeline(run_id)
        record.refresh_from_db()
        assert record.failed and "Validation error" in record.error_log


# ===============================
# Sending Stage Tests
# ===============================
class TestSendingPipeline:
    def test_sending_success(self, default_monkeypatch, valid_data, monkeypatch):
        """Test that a validated message is sent successfully."""
        pid = "user_send_success"
        run_id = individual_ingest_pipeline(pid, valid_data)
        record = get_record(run_id)
        record.validated_message = "Final response"
        record.save()
        monkeypatch.setattr("chat.services.individual_pipeline.send_message_to_participant", dummy_send_message)
        individual_send_pipeline(run_id)
        record.refresh_from_db()
        assert record.sent

    def test_sending_exception(self, default_monkeypatch, valid_data, monkeypatch):
        """Test that an exception during sending flags the record as failed."""
        pid = "user_send_exception"
        run_id = individual_ingest_pipeline(pid, valid_data)
        record = get_record(run_id)
        record.validated_message = "Final response"
        record.save()
        monkeypatch.setattr(
            "chat.services.individual_pipeline.send_message_to_participant",
            lambda pid, msg: (_ for _ in ()).throw(Exception("Send error")),
        )
        with pytest.raises(Exception, match="Send error"):
            individual_send_pipeline(run_id)
        record.refresh_from_db()
        assert record.failed and "Send error" in record.error_log


# ===============================
# Overall Pipeline Task Tests
# ===============================
class TestPipelineTask:
    def test_pipeline_task_full_success(self, default_monkeypatch, valid_data, monkeypatch):
        """Test full pipeline execution when all stages succeed."""
        pid = "user_full_success"
        individual_pipeline_task(pid, valid_data)
        record = IndividualPipelineRecord.objects.filter(participant_id=pid).order_by("-id").first()
        assert record.ingested and not record.moderated and record.processed and record.sent

    def test_pipeline_task_moderated(self, default_monkeypatch, valid_data, monkeypatch):
        """Test pipeline execution when moderation blocks the message."""
        pid = "user_pipeline_moderated"
        run_id = individual_ingest_pipeline(pid, valid_data)
        monkeypatch.setattr("chat.services.individual_pipeline.moderate_message", dummy_moderate_block)
        monkeypatch.setattr("chat.services.individual_pipeline.get_moderation_message", dummy_get_moderation_message)
        individual_moderation_pipeline(run_id)
        record = get_record(run_id)
        assert record.moderated
        monkeypatch.setattr("chat.services.individual_pipeline.send_message_to_participant", dummy_send_message)
        individual_validate_pipeline(run_id)
        individual_send_pipeline(run_id)
        record.refresh_from_db()
        assert record.sent

    def test_pipeline_task_test_user(self, default_monkeypatch, valid_data, monkeypatch):
        """Test that the pipeline does not send a message for test users."""
        pid = "user_test_user"
        monkeypatch.setattr("chat.services.individual_pipeline.is_test_user", lambda pid: True)
        individual_pipeline_task(pid, valid_data)
        record = IndividualPipelineRecord.objects.filter(participant_id=pid).order_by("-id").first()
        assert not record.sent

    def test_pipeline_task_exception_propagation(self, default_monkeypatch, valid_data, monkeypatch):
        """Test that an exception in the pipeline task propagates and flags the record as failed."""
        pid = "user_pipeline_exception"
        monkeypatch.setattr(
            "chat.services.individual_pipeline.generate_response",
            lambda h, i, m: (_ for _ in ()).throw(Exception("Processing exception in task")),
        )
        with pytest.raises(Exception, match="Processing exception in task"):
            individual_pipeline_task(pid, valid_data)
        record = IndividualPipelineRecord.objects.filter(participant_id=pid).order_by("-id").first()
        assert record.failed and "Processing exception in task" in record.error_log
