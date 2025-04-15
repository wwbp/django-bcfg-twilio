from uuid import uuid4
from django.test import override_settings
from django.urls import reverse
import pytest

from chat.models import Control, MessageType, Prompt

_INITIAL_MESSAGE = "Some initial message"
_FIRST_USER_MESSAGE = "some message from user"


@pytest.fixture
def inbound_call_and_mocks():
    group_id = uuid4()
    sender_id = uuid4()
    inbound_payload = {
        "message": _FIRST_USER_MESSAGE,
        "sender_id": sender_id,
        "context": {
            "school_name": "Test School",
            "school_mascot": "Test Mascot",
            "initial_message": _INITIAL_MESSAGE,
            "week_number": 1,
            "message_type": MessageType.INITIAL,
            "participants": [
                {
                    "name": "Participant 1",
                    "id": sender_id,
                },
                {
                    "name": "Participant 2",
                    "id": uuid4(),
                },
                {
                    "name": "Participant 3",
                    "id": uuid4(),
                },
            ],
        },
    }
    Prompt.objects.create(
        is_for_group=True,
        week=inbound_payload["context"]["week_number"],
        type=inbound_payload["context"]["message_type"],
        activity="base activity",
    )
    Control.objects.create(system="System", persona="Persona")
    return group_id, sender_id, inbound_payload


def test_group_pipeline(inbound_call_and_mocks, celery_task_always_eager, client):
    group_id, sender_id, data = inbound_call_and_mocks
    valid_api_key = "valid-api-key"
    url = reverse("chat:ingest-group", args=[group_id])
    with override_settings(INBOUND_MESSAGE_API_KEY=valid_api_key):
        response = client.post(
            url,
            data,
            content_type="application/json",
            headers={"Authorization": f"Bearer {valid_api_key}"},
        )
    assert response.status_code == 202
