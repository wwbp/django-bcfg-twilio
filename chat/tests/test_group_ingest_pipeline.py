from django.test import override_settings
from django.urls import reverse
import logging

import pytest

from chat.models import MessageType

logger = logging.getLogger(__name__)


@pytest.fixture
def ingest_payload():
    return {
        "message": "some message",
        "sender_id": "participant1",
        "context": {
            "school_name": "Test School",
            "school_mascot": "Test Mascot",
            "initial_message": "Welcome to the group!",
            "week_number": 1,
            "message_type": MessageType.INITIAL,
            "participants": [
                {
                    "name": "Participant 1",
                    "id": "participant1",
                },
            ],
        },
    }


@pytest.mark.parametrize("api_key_is_valid", [True, False])
def test_group_ingest_view_auth(client, api_key_is_valid):
    valid_api_key = "valid-api-key"

    url = reverse("chat:ingest-group", args=["group123"])
    with override_settings(INBOUND_MESSAGE_API_KEY=valid_api_key):
        response = client.post(
            url,
            "",
            content_type="application/json",
            headers={"Authorization": f"Bearer {valid_api_key if api_key_is_valid else 'invalid-api-key'}"},
        )
    # response is 400 if api key is valid as we sent no data
    assert response.status_code == (400 if api_key_is_valid else 403)


def test_group_ingest_blank_message(client, ingest_payload):
    valid_api_key = "valid-api-key"

    url = reverse("chat:ingest-group", args=["group123"])
    ingest_payload["message"] = ""
    with override_settings(INBOUND_MESSAGE_API_KEY=valid_api_key):
        response = client.post(
            url,
            ingest_payload,
            content_type="application/json",
            headers={"Authorization": f"Bearer {valid_api_key}"},
        )
    assert response.status_code == 202


def test_group_ingest_blank_initial_message(client, ingest_payload):
    valid_api_key = "valid-api-key"

    url = reverse("chat:ingest-group", args=["group123"])
    ingest_payload["context"]["initial_message"] = ""
    with override_settings(INBOUND_MESSAGE_API_KEY=valid_api_key):
        response = client.post(
            url,
            ingest_payload,
            content_type="application/json",
            headers={"Authorization": f"Bearer {valid_api_key}"},
        )
    assert response.status_code == 202
