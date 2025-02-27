import os
from kani import Kani, ChatMessage
from kani.engines.openai import OpenAIEngine


api_key = os.getenv(
    "OPENAI_API_KEY")


async def _generate_response(chat_history: list[ChatMessage], instructions: str, message: str) -> ChatMessage:
    engine = OpenAIEngine(api_key, model="gpt-4o-mini")
    assistant = Kani(engine, system_prompt=instructions,
                     chat_history=chat_history)
    response = await assistant.chat_round_str(message)
    return response


async def generate_response(history_json: list[dict], instructions: str, message: str) -> ChatMessage:
    chat_history = [ChatMessage.model_validate(chat) for chat in history_json]
    response = await _generate_response(chat_history, instructions, message)
    return response
