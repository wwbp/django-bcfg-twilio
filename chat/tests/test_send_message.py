import pytest
import httpx
from unittest.mock import patch, MagicMock
from django.conf import settings
import logging
from chat.services.send import (
    send_message_to_participant,
    send_message_to_participant_group,
    send_school_summaries_to_hub_for_week,
    send_missing_summary_notification,
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
        request = httpx.Request("POST", "http://testserver/fake-url")
        response = httpx.Response(status_code=404, request=request, text="Not Found")
        raise httpx.HTTPStatusError("error", request=request, response=response)

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


def test_send_message_to_participant_not_found_404(caplog):
    participant_id = "participant404"
    message = "Hello 404"
    expected_url = f"{settings.BCFG_DOMAIN}/ai/api/participant/{participant_id}/send"
    expected_payload = {"message": message}
    expected_headers = {"Authorization": f"Bearer {settings.BCFG_API_KEY}"}

    def raise_error():
        req = httpx.Request("POST", expected_url)
        resp = httpx.Response(status_code=404, request=req)
        raise httpx.HTTPStatusError("404 Client Error", request=req, response=resp)

    fake_response = MagicMock()
    fake_response.raise_for_status = raise_error
    mock_client = MagicMock()
    mock_client.post.return_value = fake_response

    caplog.set_level(logging.ERROR)
    with patch("chat.services.send.httpx.Client", return_value=get_client_patch(mock_client)):
        with pytest.raises(httpx.HTTPStatusError):
            send_message_to_participant(participant_id, message)

    mock_client.post.assert_called_once_with(expected_url, json=expected_payload, headers=expected_headers)
    assert (
        f"Failed to send message to participant {participant_id}: Participant {participant_id} not found (404)"
    ) in caplog.text


def test_send_message_to_participant_payload_too_large_413(caplog):
    participant_id = "participant413"
    message = "Hello 413"
    expected_url = f"{settings.BCFG_DOMAIN}/ai/api/participant/{participant_id}/send"
    expected_payload = {"message": message}
    expected_headers = {"Authorization": f"Bearer {settings.BCFG_API_KEY}"}

    def raise_error():
        req = httpx.Request("POST", expected_url)
        resp = httpx.Response(status_code=413, request=req)
        raise httpx.HTTPStatusError("413 Payload Too Large", request=req, response=resp)

    fake_response = MagicMock()
    fake_response.raise_for_status = raise_error
    mock_client = MagicMock()
    mock_client.post.return_value = fake_response

    caplog.set_level(logging.ERROR)
    with patch("chat.services.send.httpx.Client", return_value=get_client_patch(mock_client)):
        with pytest.raises(httpx.HTTPStatusError):
            send_message_to_participant(participant_id, message)

    mock_client.post.assert_called_once_with(expected_url, json=expected_payload, headers=expected_headers)
    assert (
        f"Failed to send message to participant {participant_id}: "
        f"Payload too large for participant {participant_id} (413)"
    ) in caplog.text


def test_send_message_to_participant_group_not_found_404(caplog):
    group_id = "group404"
    message = "Group hello 404"
    expected_url = f"{settings.BCFG_DOMAIN}/ai/api/participantgroup/{group_id}/send"
    expected_payload = {"message": message}
    expected_headers = {"Authorization": f"Bearer {settings.BCFG_API_KEY}"}

    def raise_error():
        req = httpx.Request("POST", expected_url)
        resp = httpx.Response(status_code=404, request=req)
        raise httpx.HTTPStatusError("404 Client Error", request=req, response=resp)

    fake_response = MagicMock()
    fake_response.raise_for_status = raise_error
    mock_client = MagicMock()
    mock_client.post.return_value = fake_response

    caplog.set_level(logging.ERROR)
    with patch("chat.services.send.httpx.Client", return_value=get_client_patch(mock_client)):
        with pytest.raises(httpx.HTTPStatusError):
            send_message_to_participant_group(group_id, message)

    mock_client.post.assert_called_once_with(expected_url, json=expected_payload, headers=expected_headers)
    assert (
        f"Failed to send message to participant group {group_id}: Participant group {group_id} not found (404)"
    ) in caplog.text


def test_send_message_to_participant_group_payload_too_large_413(caplog):
    group_id = "group413"
    message = "Group hello 413"
    expected_url = f"{settings.BCFG_DOMAIN}/ai/api/participantgroup/{group_id}/send"
    expected_payload = {"message": message}
    expected_headers = {"Authorization": f"Bearer {settings.BCFG_API_KEY}"}

    def raise_error():
        req = httpx.Request("POST", expected_url)
        resp = httpx.Response(status_code=413, request=req)
        raise httpx.HTTPStatusError("413 Payload Too Large", request=req, response=resp)

    fake_response = MagicMock()
    fake_response.raise_for_status = raise_error
    mock_client = MagicMock()
    mock_client.post.return_value = fake_response

    caplog.set_level(logging.ERROR)
    with patch("chat.services.send.httpx.Client", return_value=get_client_patch(mock_client)):
        with pytest.raises(httpx.HTTPStatusError):
            send_message_to_participant_group(group_id, message)

    mock_client.post.assert_called_once_with(expected_url, json=expected_payload, headers=expected_headers)
    assert (
        f"Failed to send message to participant group {group_id}: "
        f"Payload too large for participant group {group_id} (413)"
    ) in caplog.text


def test_send_school_summaries_to_hub_for_week_success(caplog):
    school_name = "TestSchool"
    week_number = 5
    summary_contents = ["Summary 1", "Summary 2", "Summary 3"]
    expected_url = f"{settings.BCFG_DOMAIN}/ai/api/summary/school/{school_name}/week/{week_number}"
    expected_payload = {"summaries": summary_contents}
    expected_headers = {"Authorization": f"Bearer {settings.BCFG_API_KEY}"}

    fake_response = MagicMock()
    fake_response.raise_for_status = lambda: None
    fake_response.json = lambda: {"status": "success", "message": "Summaries sent"}

    mock_client = MagicMock()
    mock_client.post.return_value = fake_response

    caplog.set_level(logging.INFO)
    with patch("chat.services.send.httpx.Client", return_value=get_client_patch(mock_client)):
        result = send_school_summaries_to_hub_for_week(school_name, week_number, summary_contents)

    mock_client.post.assert_called_once_with(expected_url, json=expected_payload, headers=expected_headers)
    assert result == {"status": "success", "message": "Summaries sent"}

    # Check that all expected log messages are present
    assert f"Sending summaries to hub for {school_name}, week {week_number}" in caplog.text
    assert f"URL: {expected_url}" in caplog.text
    assert f"Payload: {expected_payload}" in caplog.text
    assert f"Number of summaries: {len(summary_contents)}" in caplog.text
    assert f"Successfully sent summaries to hub for {school_name}, week {week_number}" in caplog.text


def test_send_school_summaries_to_hub_for_week_http_error(caplog):
    school_name = "TestSchool"
    week_number = 5
    summary_contents = ["Summary 1"]
    expected_url = f"{settings.BCFG_DOMAIN}/ai/api/summary/school/{school_name}/week/{week_number}"
    expected_payload = {"summaries": summary_contents}
    expected_headers = {"Authorization": f"Bearer {settings.BCFG_API_KEY}"}

    def raise_error():
        req = httpx.Request("POST", expected_url)
        resp = httpx.Response(status_code=500, request=req, text="Internal Server Error")
        raise httpx.HTTPStatusError("500 Internal Server Error", request=req, response=resp)

    fake_response = MagicMock()
    fake_response.raise_for_status = raise_error
    mock_client = MagicMock()
    mock_client.post.return_value = fake_response

    caplog.set_level(logging.ERROR)
    with patch("chat.services.send.httpx.Client", return_value=get_client_patch(mock_client)):
        with pytest.raises(httpx.HTTPStatusError):
            send_school_summaries_to_hub_for_week(school_name, week_number, summary_contents)

    mock_client.post.assert_called_once_with(expected_url, json=expected_payload, headers=expected_headers)
    assert f"HTTP error sending summaries to hub for {school_name}, week {week_number}" in caplog.text
    assert "Status 500" in caplog.text
    assert "Internal Server Error" in caplog.text


def test_send_school_summaries_to_hub_for_week_unexpected_error(caplog):
    school_name = "TestSchool"
    week_number = 5
    summary_contents = ["Summary 1"]
    expected_url = f"{settings.BCFG_DOMAIN}/ai/api/summary/school/{school_name}/week/{week_number}"
    expected_payload = {"summaries": summary_contents}
    expected_headers = {"Authorization": f"Bearer {settings.BCFG_API_KEY}"}

    mock_client = MagicMock()
    mock_client.post.side_effect = ValueError("Unexpected database error")

    caplog.set_level(logging.ERROR)
    with patch("chat.services.send.httpx.Client", return_value=get_client_patch(mock_client)):
        with pytest.raises(ValueError):
            send_school_summaries_to_hub_for_week(school_name, week_number, summary_contents)

    mock_client.post.assert_called_once_with(expected_url, json=expected_payload, headers=expected_headers)
    assert f"Unexpected error sending summaries to hub for {school_name}, week {week_number}" in caplog.text
    assert "Unexpected database error" in caplog.text


def test_send_missing_summary_notification_success(caplog):
    to_emails = ["admin@test.com", "user@test.com"]
    config_link = "https://example.com/config"
    missing_for = ["School1", "School2"]
    expected_url = f"{settings.BCFG_DOMAIN}/ai/api/summary/missing-alert"
    expected_payload = {"to_emails": to_emails, "config_link": config_link, "missing_for": missing_for}
    expected_headers = {"Authorization": f"Bearer {settings.BCFG_API_KEY}"}

    fake_response = MagicMock()
    fake_response.raise_for_status = lambda: None
    fake_response.json = lambda: {"status": "success", "message": "Notification sent"}

    mock_client = MagicMock()
    mock_client.post.return_value = fake_response

    caplog.set_level(logging.INFO)
    with patch("chat.services.send.httpx.Client", return_value=get_client_patch(mock_client)):
        result = send_missing_summary_notification(to_emails, config_link, missing_for)

    mock_client.post.assert_called_once_with(expected_url, json=expected_payload, headers=expected_headers)
    assert result == {"status": "success", "message": "Notification sent"}

    # Check that all expected log messages are present
    assert "Sending missing summary notification" in caplog.text
    assert f"URL: {expected_url}" in caplog.text
    assert f"To emails: {to_emails}" in caplog.text
    assert f"Missing for: {missing_for}" in caplog.text
    assert f"Config link: {config_link}" in caplog.text
    assert "Successfully sent missing summary notification" in caplog.text


def test_send_missing_summary_notification_http_error(caplog):
    to_emails = ["admin@test.com"]
    config_link = "https://example.com/config"
    missing_for = ["School1"]
    expected_url = f"{settings.BCFG_DOMAIN}/ai/api/summary/missing-alert"
    expected_payload = {"to_emails": to_emails, "config_link": config_link, "missing_for": missing_for}
    expected_headers = {"Authorization": f"Bearer {settings.BCFG_API_KEY}"}

    def raise_error():
        req = httpx.Request("POST", expected_url)
        resp = httpx.Response(status_code=400, request=req, text="Bad Request - Invalid emails")
        raise httpx.HTTPStatusError("400 Bad Request", request=req, response=resp)

    fake_response = MagicMock()
    fake_response.raise_for_status = raise_error
    mock_client = MagicMock()
    mock_client.post.return_value = fake_response

    caplog.set_level(logging.ERROR)
    with patch("chat.services.send.httpx.Client", return_value=get_client_patch(mock_client)):
        with pytest.raises(httpx.HTTPStatusError):
            send_missing_summary_notification(to_emails, config_link, missing_for)

    mock_client.post.assert_called_once_with(expected_url, json=expected_payload, headers=expected_headers)
    assert "HTTP error sending missing summary notification" in caplog.text
    assert "Status 400" in caplog.text
    assert "Bad Request - Invalid emails" in caplog.text


def test_send_missing_summary_notification_unexpected_error(caplog):
    to_emails = ["admin@test.com"]
    config_link = "https://example.com/config"
    missing_for = ["School1"]
    expected_url = f"{settings.BCFG_DOMAIN}/ai/api/summary/missing-alert"
    expected_payload = {"to_emails": to_emails, "config_link": config_link, "missing_for": missing_for}
    expected_headers = {"Authorization": f"Bearer {settings.BCFG_API_KEY}"}

    mock_client = MagicMock()
    mock_client.post.side_effect = ValueError("Invalid configuration")

    caplog.set_level(logging.ERROR)
    with patch("chat.services.send.httpx.Client", return_value=get_client_patch(mock_client)):
        with pytest.raises(ValueError):
            send_missing_summary_notification(to_emails, config_link, missing_for)

    mock_client.post.assert_called_once_with(expected_url, json=expected_payload, headers=expected_headers)
    assert "Unexpected error sending missing summary notification" in caplog.text
    assert "Invalid configuration" in caplog.text


def test_send_school_summaries_to_hub_for_week_empty_summaries(caplog):
    school_name = "TestSchool"
    week_number = 5
    summary_contents = []
    expected_url = f"{settings.BCFG_DOMAIN}/ai/api/summary/school/{school_name}/week/{week_number}"
    expected_payload = {"summaries": summary_contents}
    expected_headers = {"Authorization": f"Bearer {settings.BCFG_API_KEY}"}

    fake_response = MagicMock()
    fake_response.raise_for_status = lambda: None
    fake_response.json = lambda: {"status": "success", "message": "Empty summaries sent"}

    mock_client = MagicMock()
    mock_client.post.return_value = fake_response

    caplog.set_level(logging.INFO)
    with patch("chat.services.send.httpx.Client", return_value=get_client_patch(mock_client)):
        result = send_school_summaries_to_hub_for_week(school_name, week_number, summary_contents)

    mock_client.post.assert_called_once_with(expected_url, json=expected_payload, headers=expected_headers)
    assert result == {"status": "success", "message": "Empty summaries sent"}
    assert "Number of summaries: 0" in caplog.text


def test_send_missing_summary_notification_empty_lists(caplog):
    to_emails = []
    config_link = "https://example.com/config"
    missing_for = []
    expected_url = f"{settings.BCFG_DOMAIN}/ai/api/summary/missing-alert"
    expected_payload = {"to_emails": to_emails, "config_link": config_link, "missing_for": missing_for}
    expected_headers = {"Authorization": f"Bearer {settings.BCFG_API_KEY}"}

    fake_response = MagicMock()
    fake_response.raise_for_status = lambda: None
    fake_response.json = lambda: {"status": "success", "message": "Empty notification sent"}

    mock_client = MagicMock()
    mock_client.post.return_value = fake_response

    caplog.set_level(logging.INFO)
    with patch("chat.services.send.httpx.Client", return_value=get_client_patch(mock_client)):
        result = send_missing_summary_notification(to_emails, config_link, missing_for)

    mock_client.post.assert_called_once_with(expected_url, json=expected_payload, headers=expected_headers)
    assert result == {"status": "success", "message": "Empty notification sent"}
    assert "To emails: []" in caplog.text
    assert "Missing for: []" in caplog.text
