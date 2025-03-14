import re
from asgiref.sync import sync_to_async
import os
from openai import OpenAI
from .crud import get_moderation_message
from .moderation import moderate_message
from kani import Kani, ChatMessage
from kani.engines.openai import OpenAIEngine


api_key = os.getenv(
    "OPENAI_API_KEY")


async def _generate_response(chat_history: list[ChatMessage], instructions: str, message: str) -> str:
    blocked_str = moderate_message(message)
    if blocked_str:
        moderation_message = await sync_to_async(get_moderation_message)()
        return moderation_message
    engine = OpenAIEngine(api_key, model="gpt-4o-mini")
    assistant = Kani(engine, system_prompt=instructions,
                     chat_history=chat_history)
    response = await assistant.chat_round_str(message)
    response = await ensure_320_character_limit(response)
    return response


async def generate_response(history_json: list[dict], instructions: str, message: str) -> ChatMessage:
    chat_history = [ChatMessage.model_validate(chat) for chat in history_json]
    response = await _generate_response(chat_history, instructions, message)
    return response


async def chat_completion(instructions: str):
    client = OpenAI()
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": instructions},
        ],
    )
    response = completion.choices[0].message.content
    return response


async def ensure_320_character_limit(text: str) -> str:
    if len(text) <= 320:
        return text

    current_text = text

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
