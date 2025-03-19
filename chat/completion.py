import logging
import re
import os
import functools
import asyncio

from openai import OpenAI

from kani import Kani, ChatMessage
from kani.engines.openai import OpenAIEngine

api_key = os.getenv("OPENAI_API_KEY")

logger = logging.getLogger(__name__)


def log_exceptions(func):
    if asyncio.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                logger.info("Entering %s", func.__name__)
                return await func(*args, **kwargs)
            except Exception as e:
                logger.exception("Exception in %s: %s", func.__name__, e)
                raise
        return async_wrapper
    else:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                logger.info("Entering %s", func.__name__)
                return func(*args, **kwargs)
            except Exception as e:
                logger.exception("Exception in %s: %s", func.__name__, e)
                raise
        return sync_wrapper


@log_exceptions
async def _generate_response(
    chat_history: list[ChatMessage],
    instructions: str,
    message: str
) -> str:
    engine = OpenAIEngine(api_key, model="gpt-4o-mini")
    assistant = Kani(engine, system_prompt=instructions,
                     chat_history=chat_history)
    response = await assistant.chat_round_str(message)
    return response


@log_exceptions
async def generate_response(
    history_json: list[dict],
    instructions: str,
    message: str
) -> ChatMessage:
    chat_history = [ChatMessage.model_validate(chat) for chat in history_json]
    response = await _generate_response(chat_history, instructions, message)
    return response


@log_exceptions
async def chat_completion(instructions: str) -> str:
    client = OpenAI()
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": instructions},
        ],
    )
    response = completion.choices[0].message.content
    return response


@log_exceptions
async def ensure_320_character_limit(current_text: str) -> str:
    for _ in range(2):
        if len(current_text) > 320:
            instructions = (
                "Goal: Shorten the following text to under 320 characters. "
                "Output format: just the shortened response text.\n\nText: " + current_text
            )
            shortened = await chat_completion(instructions)
            current_text = shortened

    if len(current_text) > 320:
        sentences = re.split(r'(?<=\.)\s+', current_text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            return current_text[:320]

        while len(' '.join(sentences).strip()) > 320 and len(sentences) > 1:
            sentences.pop()
        shortened = ' '.join(sentences).strip()

        if not shortened:
            return current_text[:320]

        if len(shortened) > 320:
            shortened = shortened[:320]

        return shortened

    return current_text
