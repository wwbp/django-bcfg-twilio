from django.test import override_settings
from django.urls import reverse
import logging

import pytest

logger = logging.getLogger(__name__)


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
