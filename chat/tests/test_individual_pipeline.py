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

# --- Dummy Functions ---
def dummy_ingest(pid, data): return None
def dummy_moderate(msg): return ""
def dummy_moderate_block(msg): return "block"
def dummy_get_moderation_message(): return "moderation response"
def dummy_load_chat_history(pid): return ([], "Test Message")
def dummy_load_chat_history_mismatch(pid): return ([], "Different Message")
def dummy_load_instruction_prompt(pid): return "dummy instructions"
def dummy_generate_response(hist, instr, msg): return "LLM response"
def dummy_ensure_within_character_limit(resp): return "shortened response"
async def dummy_send_message(pid, msg): return None

# --- Fixtures ---
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

# --- Ingestion Tests ---
@pytest.mark.django_db
def test_ingest_success(default_monkeypatch, valid_data):
    pid = "user_ingest_success"
    run_id = individual_ingest_pipeline(pid, valid_data)
    record = get_record(run_id)
    assert record.participant_id == pid
    assert record.message == valid_data["message"]
    assert record.ingested and not record.failed

@pytest.mark.django_db
def test_ingest_failure(monkeypatch, valid_data):
    pid = "user_ingest_failure"
    monkeypatch.setattr("chat.services.individual_pipeline.ingest_individual_request",
                        lambda pid, data: (_ for _ in ()).throw(Exception("Ingestion error")))
    with pytest.raises(Exception, match="Ingestion error"):
        individual_ingest_pipeline(pid, valid_data)
    record = IndividualPipelineRecord.objects.filter(participant_id=pid).first()
    assert record and record.failed and "Ingestion error" in record.error_log

# --- Moderation Tests ---
@pytest.mark.django_db
def test_moderation_no_block(default_monkeypatch, valid_data):
    pid = "user_mod_no_block"
    run_id = individual_ingest_pipeline(pid, valid_data)
    individual_moderation_pipeline(run_id)
    assert not get_record(run_id).moderated

@pytest.mark.django_db
def test_moderation_block(default_monkeypatch, valid_data, monkeypatch):
    pid = "user_mod_block"
    run_id = individual_ingest_pipeline(pid, valid_data)
    monkeypatch.setattr("chat.services.individual_pipeline.moderate_message", dummy_moderate_block)
    monkeypatch.setattr("chat.services.individual_pipeline.get_moderation_message", dummy_get_moderation_message)
    individual_moderation_pipeline(run_id)
    record = get_record(run_id)
    assert record.moderated and record.response == "moderation response"

@pytest.mark.django_db
def test_moderation_exception(default_monkeypatch, valid_data, monkeypatch):
    pid = "user_mod_exception"
    run_id = individual_ingest_pipeline(pid, valid_data)
    monkeypatch.setattr("chat.services.individual_pipeline.moderate_message",
                        lambda msg: (_ for _ in ()).throw(Exception("Moderation failure")))
    with pytest.raises(Exception, match="Moderation failure"):
        individual_moderation_pipeline(run_id)
    record = get_record(run_id)
    assert record.failed and "Moderation failure" in record.error_log

# --- Processing Tests ---
@pytest.mark.django_db
def test_processing_success(default_monkeypatch, valid_data, monkeypatch):
    pid = "user_process_success"
    run_id = individual_ingest_pipeline(pid, valid_data)
    monkeypatch.setattr("chat.services.individual_pipeline.load_individual_chat_history", dummy_load_chat_history)
    monkeypatch.setattr("chat.services.individual_pipeline.load_instruction_prompt", dummy_load_instruction_prompt)
    monkeypatch.setattr("chat.services.individual_pipeline.generate_response", dummy_generate_response)
    individual_process_pipeline(run_id)
    record = get_record(run_id)
    assert record.processed and record.instruction_prompt == "dummy instructions" and record.response == "LLM response"

@pytest.mark.django_db
def test_processing_message_mismatch(default_monkeypatch, valid_data, monkeypatch):
    pid = "user_process_mismatch"
    run_id = individual_ingest_pipeline(pid, valid_data)
    monkeypatch.setattr("chat.services.individual_pipeline.load_individual_chat_history", dummy_load_chat_history_mismatch)
    individual_process_pipeline(run_id)
    assert not get_record(run_id).processed

@pytest.mark.django_db
def test_processing_exception(default_monkeypatch, valid_data, monkeypatch):
    pid = "user_process_exception"
    run_id = individual_ingest_pipeline(pid, valid_data)
    monkeypatch.setattr("chat.services.individual_pipeline.load_individual_chat_history", dummy_load_chat_history)
    monkeypatch.setattr("chat.services.individual_pipeline.load_instruction_prompt", dummy_load_instruction_prompt)
    monkeypatch.setattr("chat.services.individual_pipeline.generate_response",
                        lambda h, i, m: (_ for _ in ()).throw(Exception("Processing error")))
    with pytest.raises(Exception, match="Processing error"):
        individual_process_pipeline(run_id)
    record = get_record(run_id)
    assert record.failed and "Processing error" in record.error_log

# --- Validation Tests ---
@pytest.mark.django_db
def test_validation_within_limit(default_monkeypatch, valid_data, monkeypatch):
    pid = "user_validate_within"
    run_id = individual_ingest_pipeline(pid, valid_data)
    record = get_record(run_id)
    record.response = "Short response"
    record.save()
    monkeypatch.setattr("chat.services.individual_pipeline.save_assistant_response", lambda pid, msg: None)
    individual_validate_pipeline(run_id)
    record.refresh_from_db()
    assert record.validated_message == "Short response" and not record.shortened

@pytest.mark.django_db
def test_validation_exceeding_limit(default_monkeypatch, valid_data, monkeypatch):
    pid = "user_validate_exceed"
    run_id = individual_ingest_pipeline(pid, valid_data)
    record = get_record(run_id)
    long_resp = "X" * (MAX_RESPONSE_CHARACTER_LENGTH + 10)
    record.response = long_resp
    record.save()
    monkeypatch.setattr("chat.services.individual_pipeline.ensure_within_character_limit", dummy_ensure_within_character_limit)
    monkeypatch.setattr("chat.services.individual_pipeline.save_assistant_response", lambda pid, msg: None)
    individual_validate_pipeline(run_id)
    record.refresh_from_db()
    assert record.shortened and record.validated_message == "shortened response"

@pytest.mark.django_db
def test_validation_exception(default_monkeypatch, valid_data, monkeypatch):
    pid = "user_validate_exception"
    run_id = individual_ingest_pipeline(pid, valid_data)
    record = get_record(run_id)
    record.response = "X" * (MAX_RESPONSE_CHARACTER_LENGTH + 1)
    record.save()
    monkeypatch.setattr("chat.services.individual_pipeline.ensure_within_character_limit",
                        lambda r: (_ for _ in ()).throw(Exception("Validation error")))
    with pytest.raises(Exception, match="Validation error"):
        individual_validate_pipeline(run_id)
    record.refresh_from_db()
    assert record.failed and "Validation error" in record.error_log

# --- Sending Tests ---
@pytest.mark.django_db
def test_sending_success(default_monkeypatch, valid_data, monkeypatch):
    pid = "user_send_success"
    run_id = individual_ingest_pipeline(pid, valid_data)
    record = get_record(run_id)
    record.validated_message = "Final response"
    record.save()
    monkeypatch.setattr("chat.services.individual_pipeline.send_message_to_participant", dummy_send_message)
    individual_send_pipeline(run_id)
    record.refresh_from_db()
    assert record.sent

@pytest.mark.django_db
def test_sending_exception(default_monkeypatch, valid_data, monkeypatch):
    pid = "user_send_exception"
    run_id = individual_ingest_pipeline(pid, valid_data)
    record = get_record(run_id)
    record.validated_message = "Final response"
    record.save()
    monkeypatch.setattr("chat.services.individual_pipeline.send_message_to_participant",
                        lambda pid, msg: (_ for _ in ()).throw(Exception("Send error")))
    with pytest.raises(Exception, match="Send error"):
        individual_send_pipeline(run_id)
    record.refresh_from_db()
    assert record.failed and "Send error" in record.error_log

# --- Overall Pipeline Task ---
@pytest.mark.django_db
def test_pipeline_task_full_success(default_monkeypatch, valid_data, monkeypatch):
    pid = "user_full_success"
    individual_pipeline_task(pid, valid_data)
    record = IndividualPipelineRecord.objects.filter(participant_id=pid).order_by("-id").first()
    assert record.ingested and not record.moderated and record.processed and record.sent

@pytest.mark.django_db
def test_pipeline_task_moderated(default_monkeypatch, valid_data, monkeypatch):
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

@pytest.mark.django_db
def test_pipeline_task_test_user(default_monkeypatch, valid_data, monkeypatch):
    pid = "user_test_user"
    monkeypatch.setattr("chat.services.individual_pipeline.is_test_user", lambda pid: True)
    individual_pipeline_task(pid, valid_data)
    record = IndividualPipelineRecord.objects.filter(participant_id=pid).order_by("-id").first()
    assert not record.sent

@pytest.mark.django_db
def test_pipeline_task_exception_propagation(default_monkeypatch, valid_data, monkeypatch):
    pid = "user_pipeline_exception"
    monkeypatch.setattr("chat.services.individual_pipeline.generate_response",
                        lambda h, i, m: (_ for _ in ()).throw(Exception("Processing exception in task")))
    with pytest.raises(Exception, match="Processing exception in task"):
        individual_pipeline_task(pid, valid_data)
    record = IndividualPipelineRecord.objects.filter(participant_id=pid).order_by("-id").first()
    assert record.failed and "Processing exception in task" in record.error_log
