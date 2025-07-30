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


async def _generate_response_async(
    chat_history: list[ChatMessage], instructions: str, message: str, gpt_model: str
) -> tuple[str, int, int]:
    engine = OpenAIEngine(settings.OPENAI_API_KEY, model=gpt_model)
    try:
        assistant = Kani(engine, system_prompt=instructions, chat_history=chat_history)
        response = await assistant.chat_round_str(message)
        # response = "mocked response"
        # await asyncio.sleep(3)
        completion = await assistant.get_model_completion()
        return (
            response,
            completion.prompt_tokens or 0,
            completion.completion_tokens or 0,
        )
    finally:
        await engine.close()


def _generate_response(chat_history, instructions, message, gpt_model):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_generate_response_async(chat_history, instructions, message, gpt_model))
    finally:
        loop.close()
        asyncio.set_event_loop(None)


def generate_response(
    history_json: list[dict], instructions: str, message: str, gpt_model: str
) -> tuple[str, int | None, int | None]:
    chat_history = [ChatMessage.model_validate(chat) for chat in history_json]
    return _generate_response(chat_history, instructions, message, gpt_model)


def chat_completion(instructions: str) -> tuple[str, int, int]:
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    completion = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "user", "content": instructions},
        ],
    )
    response = completion.choices[0].message.content
    prompt_tokens = 0
    completion_tokens = 0
    if completion.usage is not None:
        prompt_tokens = completion.usage.prompt_tokens
        completion_tokens = completion.usage.completion_tokens
    return (response or "", prompt_tokens, completion_tokens)


def ensure_within_character_limit(record: BasePipelineRecord) -> str:
    if not record.response:
        return ""
    current_text = record.response
    if len(current_text) <= MAX_RESPONSE_CHARACTER_LENGTH:
        return current_text
    for _ in range(2):
        if len(current_text) > MAX_RESPONSE_CHARACTER_LENGTH:
            instructions = (
                f"Goal: Shorten the following text to under {MAX_RESPONSE_CHARACTER_LENGTH} characters. "
                "Output format: just the shortened response text.\n\nText: " + current_text
            )
            shortened, prompt_tokens, completion_tokens = chat_completion(instructions)
            current_text = shortened
            record.shorten_count += 1
            record.prompt_tokens = (record.prompt_tokens or 0) + (prompt_tokens or 0)
            record.completion_tokens = (record.completion_tokens or 0) + (completion_tokens or 0)

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
