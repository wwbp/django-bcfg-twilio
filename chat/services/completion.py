import logging
import re
import asyncio

from django.conf import settings
from chat.models import BasePipelineRecord
from openai import OpenAI

from kani import Kani, ChatMessage
from kani.engines.openai import OpenAIEngine

logger = logging.getLogger(__name__)

MAX_RESPONSE_CHARACTER_LENGTH = 320


async def _generate_response_async(chat_history: list[ChatMessage], instructions: str, message: str) -> str:
    engine = OpenAIEngine(settings.OPENAI_API_KEY, model=settings.OPENAI_MODEL)
    assistant = Kani(engine, system_prompt=instructions, chat_history=chat_history)
    response = await assistant.chat_round_str(message)
    return response


def _generate_response(chat_history: list[ChatMessage], instructions: str, message: str) -> str:
    return asyncio.run(_generate_response_async(chat_history, instructions, message))


def generate_response(history_json: list[dict], instructions: str, message: str) -> ChatMessage:
    chat_history = [ChatMessage.model_validate(chat) for chat in history_json]
    response = _generate_response(chat_history, instructions, message)
    return response


def chat_completion(instructions: str) -> str:
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    completion = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "user", "content": instructions},
        ],
    )
    response = completion.choices[0].message.content
    return response or ""


def ensure_within_character_limit(record: BasePipelineRecord) -> str:
    current_text = record.response
    if len(current_text) <= MAX_RESPONSE_CHARACTER_LENGTH:
        return current_text
    for _ in range(2):
        if len(current_text) > MAX_RESPONSE_CHARACTER_LENGTH:
            instructions = (
                f"Goal: Shorten the following text to under {MAX_RESPONSE_CHARACTER_LENGTH} characters. "
                "Output format: just the shortened response text.\n\nText: " + current_text
            )
            shortened = chat_completion(instructions)
            current_text = shortened
            record.shorten_count += 1

    if len(current_text) > MAX_RESPONSE_CHARACTER_LENGTH:
        sentences = re.split(r"(?<=\.)\s+", current_text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            return current_text[:MAX_RESPONSE_CHARACTER_LENGTH]

        while len(" ".join(sentences).strip()) > MAX_RESPONSE_CHARACTER_LENGTH and len(sentences) > 1:
            sentences.pop()
        shortened = " ".join(sentences).strip()

        if not shortened:
            return current_text[:MAX_RESPONSE_CHARACTER_LENGTH]

        if len(shortened) > MAX_RESPONSE_CHARACTER_LENGTH:
            shortened = shortened[:MAX_RESPONSE_CHARACTER_LENGTH]

        return shortened

    return current_text
