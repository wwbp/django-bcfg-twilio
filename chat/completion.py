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
