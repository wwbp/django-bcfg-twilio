import json
import pytest
from django.urls import reverse
from chat.services.individual_pipeline import individual_ingest_pipeline
from chat.models import IndividualPipelineRecord


@pytest.mark.django_db
def test_ingest_individual_valid(client, monkeypatch):
    # Monkeypatch the Celery task to avoid executing the actual background job.
    def fake_individual_pipeline_task_delay(id, validated_data):
        return True

    monkeypatch.setattr("chat.views.individual_pipeline_task.delay", fake_individual_pipeline_task_delay)

    url = reverse("chat:ingest-individual", args=["user123"])
    payload = {
        "context": {
            "school_name": "Test School",
            "school_mascot": "Tiger",
            "initial_message": "Welcome!",
            "week_number": 1,
            "name": "John Doe",
        },
        "message": "Hello, world!",
    }
    response = client.post(url, json.dumps(payload), content_type="application/json")
    assert response.status_code == 202
    assert response.json() == {"message": "Data received"}


@pytest.mark.django_db
def test_ingest_individual_invalid_missing_message(client):
    url = reverse("chat:ingest-individual", args=["user123"])
    # Missing the required "message" field.
    payload = {
        "context": {
            "school_name": "Test School",
            "school_mascot": "Tiger",
            "initial_message": "Welcome!",
            "week_number": 1,
            "name": "John Doe",
        }
    }
    response = client.post(url, json.dumps(payload), content_type="application/json")
    assert response.status_code == 400
    response_data = response.json()
    # Validate that the error indicates the missing 'message' field.
    assert "message" in response_data or "This field is required" in str(response_data)


@pytest.mark.django_db
def test_ingest_individual_invalid_missing_context(client):
    url = reverse("chat:ingest-individual", args=["user123"])
    # Missing the required "context" field.
    payload = {"message": "Hello, world!"}
    response = client.post(url, json.dumps(payload), content_type="application/json")
    assert response.status_code == 400
    response_data = response.json()
    # Validate that the error indicates the missing 'context' field.
    assert "context" in response_data or "This field is required" in str(response_data)


@pytest.mark.django_db
def test_ingest_individual_invalid_missing_context_field(client):
    url = reverse("chat:ingest-individual", args=["user123"])
    # The 'context' is missing one required field, e.g., "school_mascot"
    payload = {
        "context": {
            "school_name": "Test School",
            # "school_mascot": "Tiger",  # intentionally omitted
            "initial_message": "Welcome!",
            "week_number": 1,
            "name": "John Doe",
        },
        "message": "Hello, world!",
    }
    response = client.post(url, json.dumps(payload), content_type="application/json")
    assert response.status_code == 400
    response_data = response.json()
    # Validate that the error indicates the missing 'school_mascot' field.
    assert "school_mascot" in response_data or "This field is required" in str(response_data)



@pytest.mark.django_db
def test_individual_ingest_pipeline_success(monkeypatch):
    participant_id = "test_user"
    data = {"message": "hello world"}

    # Flag to verify that our fake function is actually called.
    called = False

    def fake_ingest_individual_request(pid, data_in):
        nonlocal called
        called = True
        # Simulate a successful ingest without side effects.

    # Monkeypatch the ingest_individual_request function used by individual_ingest_pipeline.
    monkeypatch.setattr("chat.services.individual_pipeline.ingest_individual_request", fake_ingest_individual_request)

    # Call the pipeline function.
    run_id = individual_ingest_pipeline(participant_id, data)

    # Assert that our fake function was called.
    assert called, "Expected ingest_individual_request to be called."

    # Assert that a new record was created with the expected values.
    record = IndividualPipelineRecord.objects.get(run_id=run_id)
    assert record.participant_id == participant_id
    assert record.ingested is True
    assert record.message == data["message"]
    assert record.failed is False
    assert record.error_log == ""


@pytest.mark.django_db
def test_individual_ingest_pipeline_failure(monkeypatch):
    participant_id = "test_user"
    data = {"message": "hello world"}

    # Create a fake function that raises an exception to simulate a failure.
    def fake_ingest_individual_request(pid, data_in):
        raise Exception("Simulated ingest error")

    monkeypatch.setattr("chat.services.individual_pipeline.ingest_individual_request", fake_ingest_individual_request)

    # Expect the pipeline to raise an exception.
    with pytest.raises(Exception, match="Simulated ingest error"):
        individual_ingest_pipeline(participant_id, data)

    # Verify that a record was created with the failure flag and proper error log.
    record = IndividualPipelineRecord.objects.last()
    assert record.participant_id == participant_id
    assert record.failed is True
    assert record.ingested is False
    assert "Simulated ingest error" in record.error_log
