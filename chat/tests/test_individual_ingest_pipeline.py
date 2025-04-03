import json
from django.urls import reverse
from unittest.mock import patch
import logging

logger = logging.getLogger(__name__)


@patch("chat.views.individual_pipeline.delay")
def test_ingest_individual_valid(mock_individual_pipeline_task_delay, client):
    # Configure the mock to return True
    mock_individual_pipeline_task_delay.return_value = True

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
    assert "message" in response_data
    assert "This field is required" in response_data["message"][0]


def test_ingest_individual_invalid_missing_context(client):
    url = reverse("chat:ingest-individual", args=["user123"])
    # Missing the required "context" field.
    payload = {"message": "Hello, world!"}
    response = client.post(url, json.dumps(payload), content_type="application/json")
    assert response.status_code == 400
    response_data = response.json()
    # Validate that the error indicates the missing 'context' field.
    assert "context" in response_data or "This field is required" in str(response_data)


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
