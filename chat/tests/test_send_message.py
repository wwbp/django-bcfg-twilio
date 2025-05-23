import pytest
import httpx
from unittest.mock import patch, MagicMock
from django.conf import settings

from chat.services.send import (
    send_moderation_message,
    send_message_to_participant,
    send_message_to_participant_group,
)


# Helper class to simulate httpx.Client as a context manager.
class FakeClientContextManager:
    def __init__(self, client):
        self.client = client

    def __enter__(self):
        return self.client

    def __exit__(self, exc_type, exc_value, traceback):
        pass


def get_client_patch(mock_client):
    return FakeClientContextManager(mock_client)


def test_send_message_to_participant_success():
    participant_id = "participant1"
    message = "Hello"
    expected_url = f"{settings.BCFG_DOMAIN}/ai/api/participant/{participant_id}/send"
    expected_payload = {"message": message}
    expected_headers = {"Authorization": f"Bearer {settings.BCFG_API_KEY}"}

    # Create a fake response simulating a successful API call.
    fake_response = MagicMock()
    fake_response.raise_for_status = lambda: None
    fake_response.json = lambda: {"status": "ok"}

    # Create a mock client with the post method returning the fake response.
    mock_client = MagicMock()
    mock_client.post.return_value = fake_response

    with patch("chat.services.send.httpx.Client", return_value=get_client_patch(mock_client)):
        result = send_message_to_participant(participant_id, message)
        mock_client.post.assert_called_once_with(expected_url, json=expected_payload, headers=expected_headers)
        assert result == {"status": "ok"}


def test_send_message_to_participant_http_status_error():
    participant_id = "participant2"
    message = "Error message"
    expected_url = f"{settings.BCFG_DOMAIN}/ai/api/participant/{participant_id}/send"
    expected_payload = {"message": message}
    expected_headers = {"Authorization": f"Bearer {settings.BCFG_API_KEY}"}

    # Create a fake response that raises HTTPStatusError on calling raise_for_status.
    def raise_error():
        raise httpx.HTTPStatusError(
            "error", request=None, response=type("FakeResponse", (), {"status_code": 400, "text": "Bad Request"})()
        )

    fake_response = MagicMock()
    fake_response.raise_for_status = raise_error

    mock_client = MagicMock()
    mock_client.post.return_value = fake_response

    with patch("chat.services.send.httpx.Client", return_value=get_client_patch(mock_client)):
        with pytest.raises(httpx.HTTPStatusError):
            send_message_to_participant(participant_id, message)
        mock_client.post.assert_called_once_with(expected_url, json=expected_payload, headers=expected_headers)


def test_send_message_to_participant_request_error():
    participant_id = "participant3"
    message = "Request error"
    expected_url = f"{settings.BCFG_DOMAIN}/ai/api/participant/{participant_id}/send"
    expected_payload = {"message": message}
    expected_headers = {"Authorization": f"Bearer {settings.BCFG_API_KEY}"}

    mock_client = MagicMock()
    # Simulate that the post call raises a RequestError.
    mock_client.post.side_effect = httpx.RequestError("Connection error")

    with patch("chat.services.send.httpx.Client", return_value=get_client_patch(mock_client)):
        with pytest.raises(httpx.RequestError):
            send_message_to_participant(participant_id, message)
        mock_client.post.assert_called_once_with(expected_url, json=expected_payload, headers=expected_headers)


def test_send_message_to_participant_group_success():
    group_id = "group1"
    message = "Group hello"
    expected_url = f"{settings.BCFG_DOMAIN}/ai/api/participantgroup/{group_id}/send"
    expected_payload = {"message": message}
    expected_headers = {"Authorization": f"Bearer {settings.BCFG_API_KEY}"}

    fake_response = MagicMock()
    fake_response.raise_for_status = lambda: None
    fake_response.json = lambda: {"status": "group ok"}

    mock_client = MagicMock()
    mock_client.post.return_value = fake_response

    with patch("chat.services.send.httpx.Client", return_value=get_client_patch(mock_client)):
        result = send_message_to_participant_group(group_id, message)
        mock_client.post.assert_called_once_with(expected_url, json=expected_payload, headers=expected_headers)
        assert result == {"status": "group ok"}


def test_send_message_to_participant_group_http_status_error():
    group_id = "group2"
    message = "Group error"
    expected_url = f"{settings.BCFG_DOMAIN}/ai/api/participantgroup/{group_id}/send"
    expected_payload = {"message": message}
    expected_headers = {"Authorization": f"Bearer {settings.BCFG_API_KEY}"}

    def raise_error():
        raise httpx.HTTPStatusError(
            "error", request=None, response=type("FakeResponse", (), {"status_code": 404, "text": "Not Found"})()
        )

    fake_response = MagicMock()
    fake_response.raise_for_status = raise_error

    mock_client = MagicMock()
    mock_client.post.return_value = fake_response

    with patch("chat.services.send.httpx.Client", return_value=get_client_patch(mock_client)):
        with pytest.raises(httpx.HTTPStatusError):
            send_message_to_participant_group(group_id, message)
        mock_client.post.assert_called_once_with(expected_url, json=expected_payload, headers=expected_headers)


def test_send_message_to_participant_group_request_error():
    group_id = "group3"
    message = "Group request error"
    expected_url = f"{settings.BCFG_DOMAIN}/ai/api/participantgroup/{group_id}/send"
    expected_payload = {"message": message}
    expected_headers = {"Authorization": f"Bearer {settings.BCFG_API_KEY}"}

    mock_client = MagicMock()
    mock_client.post.side_effect = httpx.RequestError("Timeout error")

    with patch("chat.services.send.httpx.Client", return_value=get_client_patch(mock_client)):
        with pytest.raises(httpx.RequestError):
            send_message_to_participant_group(group_id, message)
        mock_client.post.assert_called_once_with(expected_url, json=expected_payload, headers=expected_headers)


def test_individual_send_moderation_success():
    participant_id = "participant_mod_success"
    expected_url = f"{settings.BCFG_DOMAIN}/ai/api/participant/{participant_id}/safety-plan/send"
    expected_headers = {"Authorization": f"Bearer {settings.BCFG_API_KEY}"}

    fake_response = MagicMock()
    fake_response.raise_for_status = lambda: None
    fake_response.json = lambda: {"status": "moderation ok"}

    mock_client = MagicMock()
    mock_client.post.return_value = fake_response

    with patch("chat.services.send.httpx.Client", return_value=get_client_patch(mock_client)):
        result = send_moderation_message(participant_id)
        mock_client.post.assert_called_once_with(expected_url, headers=expected_headers)
        assert result == {"status": "moderation ok"}


def test_individual_send_moderation_http_status_error():
    participant_id = "participant_mod_error"
    expected_url = f"{settings.BCFG_DOMAIN}/ai/api/participant/{participant_id}/safety-plan/send"
    expected_headers = {"Authorization": f"Bearer {settings.BCFG_API_KEY}"}

    def raise_error():
        raise httpx.HTTPStatusError(
            "error",
            request=None,
            response=type("FakeResponse", (), {"status_code": 500, "text": "Internal Server Error"})(),
        )

    fake_response = MagicMock()
    fake_response.raise_for_status = raise_error

    mock_client = MagicMock()
    mock_client.post.return_value = fake_response

    with patch("chat.services.send.httpx.Client", return_value=get_client_patch(mock_client)):
        with pytest.raises(httpx.HTTPStatusError):
            send_moderation_message(participant_id)
        mock_client.post.assert_called_once_with(expected_url, headers=expected_headers)


def test_individual_send_moderation_request_error():
    participant_id = "participant_mod_request_error"
    expected_url = f"{settings.BCFG_DOMAIN}/ai/api/participant/{participant_id}/safety-plan/send"
    expected_headers = {"Authorization": f"Bearer {settings.BCFG_API_KEY}"}

    mock_client = MagicMock()
    mock_client.post.side_effect = httpx.RequestError("Network error")

    with patch("chat.services.send.httpx.Client", return_value=get_client_patch(mock_client)):
        with pytest.raises(httpx.RequestError):
            send_moderation_message(participant_id)
        mock_client.post.assert_called_once_with(expected_url, headers=expected_headers)
