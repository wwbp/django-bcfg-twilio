# File: tests/test_individual_ingest_pipeline.py
import pytest
from chat.services.individual_pipeline import individual_ingest_pipeline, IndividualPipelineRecord


# Dummy model instance to simulate a record.
class DummyRecord:
    def __init__(self, run_id, participant_id, ingested=None, message=None, failed=None, error_log=None):
        self.run_id = run_id
        self.participant_id = participant_id
        self.ingested = ingested
        self.message = message
        self.failed = failed
        self.error_log = error_log

    def save(self):
        # Simulate a model save() (can be left empty)
        pass


@pytest.fixture
def dummy_record_manager(monkeypatch):
    """
    This fixture replaces the `objects` manager on IndividualPipelineRecord with
    a dummy version that records calls to .create() so we can inspect them.
    """
    created_records = []

    def dummy_create(**kwargs):
        # Set run_id based on whether this is a success or failure record.
        run_id = "error-run-id" if kwargs.get("failed", False) else "success-run-id"
        record = DummyRecord(run_id=run_id, **kwargs)
        created_records.append(record)
        return record

    # Create a dummy objects manager with a create method.
    dummy_objects = type("DummyObjects", (), {"create": dummy_create})
    # Patch the IndividualPipelineRecord.objects to use the dummy objects.
    monkeypatch.setattr(IndividualPipelineRecord, "objects", dummy_objects)
    return created_records


def test_individual_ingest_pipeline_success(monkeypatch, dummy_record_manager):
    """
    Test that when ingest_individual_request succeeds, the pipeline creates
    a record with the expected attributes and returns the run_id.
    """
    participant_id = "test_participant_success"
    data = {"message": "Hello, world!"}

    # Patch ingest_individual_request to simulate a successful ingestion.
    def dummy_ingest_individual_request(pid, d):
        # Simply do nothing, simulating a successful operation.
        pass

    monkeypatch.setattr("chat.services.individual_pipeline.ingest_individual_request", dummy_ingest_individual_request)

    # Call the pipeline function.
    run_id = individual_ingest_pipeline(participant_id, data)

    # Verify that the function returns the run_id from the created record.
    assert run_id == "success-run-id"

    # Verify that a record was created with the correct attributes.
    assert len(dummy_record_manager) == 1
    record = dummy_record_manager[0]
    assert record.participant_id == participant_id
    assert record.ingested is True
    assert record.message == data.get("message")
    assert record.failed is False
    assert record.error_log == ""


def test_individual_ingest_pipeline_failure(monkeypatch, dummy_record_manager):
    """
    Test that when ingest_individual_request raises an exception, the pipeline:
      - Creates a failure record with an appropriate error_log.
      - Re-raises the exception.
    """
    participant_id = "test_participant_failure"
    data = {"message": "This will fail"}

    # Patch ingest_individual_request to simulate an error.
    def dummy_ingest_individual_request(pid, d):
        raise ValueError("Simulated ingestion error")

    monkeypatch.setattr("chat.services.individual_pipeline.ingest_individual_request", dummy_ingest_individual_request)

    # Verify that the function re-raises the error.
    with pytest.raises(ValueError, match="Simulated ingestion error"):
        individual_ingest_pipeline(participant_id, data)

    # Verify that a failure record was created in the except block.
    assert len(dummy_record_manager) == 1
    record = dummy_record_manager[0]
    assert record.participant_id == participant_id
    assert record.failed is True
    assert "Simulated ingestion error" in record.error_log
