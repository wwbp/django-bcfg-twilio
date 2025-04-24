import logging
from django.conf import settings
import httpx

logger = logging.getLogger(__name__)


def send_message_to_participant(participant_id: str, message: str):
    """
    Sends a message to a single participant via the BCFG endpoint.

    Endpoint:
      POST /ai/api/participant/{id}/send
    Body:
      { "message": "What a lovely day" }
    """
    url = f"{settings.BCFG_DOMAIN}/ai/api/participant/{participant_id}/send"
    payload = {"message": message}
    headers = {"Authorization": f"Bearer {settings.BCFG_API_KEY}"}
    with httpx.Client() as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


def send_message_to_participant_group(group_id: str, message: str):
    """
    Sends a message to a participant group via the BCFG endpoint.

    Endpoint:
      POST /ai/api/participantgroup/{id}/send
    """
    url = f"{settings.BCFG_DOMAIN}/ai/api/participantgroup/{group_id}/send"
    payload = {"message": message}
    headers = {"Authorization": f"Bearer {settings.BCFG_API_KEY}"}
    with httpx.Client() as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


def send_moderation_message(participant_id):
    """
    Sends a moderation message to a single participant via the BCFG endpoint.

    Endpoint:
      POST /ai/api/participant/{id}/safety-plan/send
    """
    url = f"{settings.BCFG_DOMAIN}/ai/api/participant/{participant_id}/safety-plan/send"
    headers = {"Authorization": f"Bearer {settings.BCFG_API_KEY}"}
    with httpx.Client() as client:
        response = client.post(url, headers=headers)
        response.raise_for_status()
        return response.json()


def send_school_summaries_to_hub_for_week(school_name: str, week_number: int, summary_contents: list[str]):
    url = f"{settings.BCFG_DOMAIN}/ai/api/summary/school/{school_name}/week/{week_number}"
    headers = {"Authorization": f"Bearer {settings.BCFG_API_KEY}"}
    payload = {"summaries": summary_contents}
    with httpx.Client() as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
