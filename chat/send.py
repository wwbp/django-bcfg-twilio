import httpx
import os

BCFG_DOMAIN = os.getenv("BCFG_DOMAIN", "https://bcfg-domain.com")


async def send_message_to_participant(participant_id: str, message: str):
    """
    Sends a message to a single participant via the BCFG endpoint.

    Endpoint:
      POST /ai/api/participant/{id}/send
    Body:
      { "message": "What a lovely day" }
    """
    url = f"{BCFG_DOMAIN}/ai/api/participant/{participant_id}/send"
    payload = {"message": message}
    headers = {
        "Authorization": "Bearer JLGasdfJH8lkdasop93q4lkjsedf56012879lksdfhgsd" # TODO: sync with bcfg on managing authentication tokens
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        # Log the HTTP error details and return a default value
        print(
            f"HTTP error sending message to participant {participant_id}: {exc.response.status_code} - {exc.response.text}")
        return {"error": "HTTPStatusError", "details": str(exc)}
    except httpx.RequestError as exc:
        # Log connection related errors
        print(
            f"Request error sending message to participant {participant_id}: {exc}")
        return {"error": "RequestError", "details": str(exc)}


async def send_message_to_participant_group(group_id: str, message: str):
    """
    Sends a message to a participant group via the BCFG endpoint.

    Endpoint:
      POST /ai/api/participantgroup/{id}/send
    Body:
      { "message": "What a lovely day" }
    """
    url = f"{BCFG_DOMAIN}/ai/api/participantgroup/{group_id}/send"
    payload = {"message": message}
    headers = {
        "Authorization": "Bearer JLGasdfJH8lkdasop93q4lkjsedf56012879lksdfhgsd"
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        # Log the HTTP error details and return a default value
        print(
            f"HTTP error sending message to participant group {group_id}: {exc.response.status_code} - {exc.response.text}")
        return {"error": "HTTPStatusError", "details": str(exc)}
    except httpx.RequestError as exc:
        # Log connection related errors
        print(
            f"Request error sending message to participant group {group_id}: {exc}")
        return {"error": "RequestError", "details": str(exc)}
