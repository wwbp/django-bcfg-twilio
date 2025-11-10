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
    try:
      with httpx.Client() as client:
          response = client.post(url, json=payload, headers=headers)
          response.raise_for_status()
          return response.json()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response else None
        # 404 = no such participant / opted-out; 413 = payload too big
        msg = (
            f"Participant {participant_id} not found (404)" if status == 404 else
            f"Payload too large for participant {participant_id} (413)" if status == 413 else
            f"HTTP error {status}"
        )
        logger.error(f"Failed to send message to participant {participant_id}: {msg}")
        raise

def send_message_to_participant_group(group_id: str, message: str):
    """
    Sends a message to a participant group via the BCFG endpoint.

    Endpoint:
      POST /ai/api/participantgroup/{id}/send
    """
    url = f"{settings.BCFG_DOMAIN}/ai/api/participantgroup/{group_id}/send"
    payload = {"message": message}
    headers = {"Authorization": f"Bearer {settings.BCFG_API_KEY}"}
    try:
      with httpx.Client() as client:
          response = client.post(url, json=payload, headers=headers)
          response.raise_for_status()
          return response.json()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response else None
        # 404 = no such group / opted-out; 413 = payload too big
        msg = (
            f"Participant group {group_id} not found (404)" if status == 404 else
            f"Payload too large for participant group {group_id} (413)" if status == 413 else
            f"HTTP error {status}"
        )
        logger.error(f"Failed to send message to participant group {group_id}: {msg}")
        raise

def send_school_summaries_to_hub_for_week(school_name: str, week_number: int, summary_contents: list[str]):
    url = f"{settings.BCFG_DOMAIN}/ai/api/summary/school/{school_name}/week/{week_number}"
    headers = {"Authorization": f"Bearer {settings.BCFG_API_KEY}"}
    payload = {"summaries": summary_contents}

    logger.info(f"Sending summaries to hub for {school_name}, week {week_number}")
    logger.info(f"URL: {url}")
    logger.info(f"Payload: {payload}")
    logger.info(f"Number of summaries: {len(summary_contents)}")

    try:
        with httpx.Client() as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.info(
                f"Successfully sent summaries to hub for {school_name}, week {week_number}. Response: {response.json()}"
            )
            return response.json()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response else None
        logger.error(
            f"HTTP error sending summaries to hub for {school_name}, week {week_number}: "
            f"Status {status}, Response: "
            f"{exc.response.text if exc.response else 'No response'}"
        )
        raise
    except Exception as e:
        logger.error(f"Unexpected error sending summaries to hub for {school_name}, week {week_number}: {str(e)}")
        raise


def send_missing_summary_notification(to_emails: list[str], config_link: str, missing_for: list[str]):
    url = f"{settings.BCFG_DOMAIN}/ai/api/summary/missing-alert"
    headers = {"Authorization": f"Bearer {settings.BCFG_API_KEY}"}
    payload = {"to_emails": to_emails, "config_link": config_link, "missing_for": missing_for}

    logger.info("Sending missing summary notification")
    logger.info(f"URL: {url}")
    logger.info(f"To emails: {to_emails}")
    logger.info(f"Missing for: {missing_for}")
    logger.info(f"Config link: {config_link}")

    try:
        with httpx.Client() as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.info(f"Successfully sent missing summary notification. Response: {response.json()}")
            return response.json()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response else None
        logger.error(
            (
                f"HTTP error sending missing summary notification: Status {status}, "
                f"Response: {exc.response.text if exc.response else 'No response'}"
            )
        )
        raise
    except Exception as e:
        logger.error(f"Unexpected error sending missing summary notification: {str(e)}")
        raise
