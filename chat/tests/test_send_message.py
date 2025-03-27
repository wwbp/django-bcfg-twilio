import pytest
import httpx
from unittest.mock import patch, AsyncMock

from chat.services.send import (
    BCFG_DOMAIN,
    send_message_to_participant,
    send_message_to_participant_group,
)


# Helper function to patch AsyncClient as an async context manager.
def get_async_client_patch(mock_client):
    client_cm = AsyncMock()
    client_cm.__aenter__.return_value = mock_client
    return client_cm


# Tests for send_message_to_participant


@pytest.mark.asyncio
async def test_send_message_to_participant_success():
    participant_id = "participant1"
    message = "Hello"
    expected_url = f"{BCFG_DOMAIN}/ai/api/participant/{participant_id}/send"
    expected_payload = {"message": message}
    expected_headers = {"Authorization": "Bearer JLGasdfJH8lkdasop93q4lkjsedf56012879lksdfhgsd"}

    # Create a fake response that simulates a successful API call.
    fake_response = AsyncMock()
    # Simulate synchronous behavior by using lambdas.
    fake_response.raise_for_status = lambda: None
    fake_response.json = lambda: {"status": "ok"}

    # Create a mock client whose post method returns the fake response.
    mock_client = AsyncMock()
    mock_client.post.return_value = fake_response

    with patch("chat.services.send.httpx.AsyncClient", return_value=get_async_client_patch(mock_client)):
        result = await send_message_to_participant(participant_id, message)
        mock_client.post.assert_awaited_once_with(expected_url, json=expected_payload, headers=expected_headers)
        assert result == {"status": "ok"}


@pytest.mark.asyncio
async def test_send_message_to_participant_http_status_error():
    participant_id = "participant2"
    message = "Error message"
    expected_url = f"{BCFG_DOMAIN}/ai/api/participant/{participant_id}/send"
    expected_payload = {"message": message}
    expected_headers = {"Authorization": "Bearer JLGasdfJH8lkdasop93q4lkjsedf56012879lksdfhgsd"}

    # Create a fake response that raises HTTPStatusError when raise_for_status is called.
    def raise_error():
        raise httpx.HTTPStatusError(
            "error", request=None, response=type("FakeResponse", (), {"status_code": 400, "text": "Bad Request"})
        )

    fake_response = AsyncMock()
    fake_response.raise_for_status = raise_error

    mock_client = AsyncMock()
    mock_client.post.return_value = fake_response

    with patch("chat.services.send.httpx.AsyncClient", return_value=get_async_client_patch(mock_client)):
        result = await send_message_to_participant(participant_id, message)
        mock_client.post.assert_awaited_once_with(expected_url, json=expected_payload, headers=expected_headers)
        # The function should catch the error and return a dict.
        assert result.get("error") == "HTTPStatusError"


@pytest.mark.asyncio
async def test_send_message_to_participant_request_error():
    participant_id = "participant3"
    message = "Request error"
    expected_url = f"{BCFG_DOMAIN}/ai/api/participant/{participant_id}/send"
    expected_payload = {"message": message}
    expected_headers = {"Authorization": "Bearer JLGasdfJH8lkdasop93q4lkjsedf56012879lksdfhgsd"}

    mock_client = AsyncMock()
    # Simulate that the post call raises a RequestError.
    mock_client.post.side_effect = httpx.RequestError("Connection error")

    with patch("chat.services.send.httpx.AsyncClient", return_value=get_async_client_patch(mock_client)):
        result = await send_message_to_participant(participant_id, message)
        mock_client.post.assert_awaited_once_with(expected_url, json=expected_payload, headers=expected_headers)
        assert result.get("error") == "RequestError"


# Tests for send_message_to_participant_group


@pytest.mark.asyncio
async def test_send_message_to_participant_group_success():
    group_id = "group1"
    message = "Group hello"
    expected_url = f"{BCFG_DOMAIN}/ai/api/participantgroup/{group_id}/send"
    expected_payload = {"message": message}
    expected_headers = {"Authorization": "Bearer JLGasdfJH8lkdasop93q4lkjsedf56012879lksdfhgsd"}

    fake_response = AsyncMock()
    fake_response.raise_for_status = lambda: None
    fake_response.json = lambda: {"status": "group ok"}

    mock_client = AsyncMock()
    mock_client.post.return_value = fake_response

    with patch("chat.services.send.httpx.AsyncClient", return_value=get_async_client_patch(mock_client)):
        result = await send_message_to_participant_group(group_id, message)
        mock_client.post.assert_awaited_once_with(expected_url, json=expected_payload, headers=expected_headers)
        assert result == {"status": "group ok"}


@pytest.mark.asyncio
async def test_send_message_to_participant_group_http_status_error():
    group_id = "group2"
    message = "Group error"
    expected_url = f"{BCFG_DOMAIN}/ai/api/participantgroup/{group_id}/send"
    expected_payload = {"message": message}
    expected_headers = {"Authorization": "Bearer JLGasdfJH8lkdasop93q4lkjsedf56012879lksdfhgsd"}

    def raise_error():
        raise httpx.HTTPStatusError(
            "error", request=None, response=type("FakeResponse", (), {"status_code": 404, "text": "Not Found"})
        )

    fake_response = AsyncMock()
    fake_response.raise_for_status = raise_error

    mock_client = AsyncMock()
    mock_client.post.return_value = fake_response

    with patch("chat.services.send.httpx.AsyncClient", return_value=get_async_client_patch(mock_client)):
        result = await send_message_to_participant_group(group_id, message)
        mock_client.post.assert_awaited_once_with(expected_url, json=expected_payload, headers=expected_headers)
        assert result.get("error") == "HTTPStatusError"


@pytest.mark.asyncio
async def test_send_message_to_participant_group_request_error():
    group_id = "group3"
    message = "Group request error"
    expected_url = f"{BCFG_DOMAIN}/ai/api/participantgroup/{group_id}/send"
    expected_payload = {"message": message}
    expected_headers = {"Authorization": "Bearer JLGasdfJH8lkdasop93q4lkjsedf56012879lksdfhgsd"}

    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.RequestError("Timeout error")

    with patch("chat.services.send.httpx.AsyncClient", return_value=get_async_client_patch(mock_client)):
        result = await send_message_to_participant_group(group_id, message)
        mock_client.post.assert_awaited_once_with(expected_url, json=expected_payload, headers=expected_headers)
        assert result.get("error") == "RequestError"
