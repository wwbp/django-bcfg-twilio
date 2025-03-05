import os
from .moderation import moderate_message
from kani import Kani, ChatMessage
from kani.engines.openai import OpenAIEngine


api_key = os.getenv(
    "OPENAI_API_KEY")


async def _generate_response(chat_history: list[ChatMessage], instructions: str, message: str) -> str:
    blocked_str = moderate_message(message)
    if blocked_str:
        return """I'm really sorry you're feeling this way, but I'm not equipped to help. It's important to talk to someone who can support you right now. Please contact UCLA resources such as UCLA CAPS: Counseling & Psychological Services | Counseling and Psychological Services (ucla.edu) at 310-825-0768, or the National Suicide Prevention Lifeline at 1-800-273-TALK (8255) or text HOME to 741741 to connect with a trained clinician. If you're in immediate danger, please call 911 or go to the nearest emergency room. Please also note that if you wish not to continue with the study, feel free to quit anytime."""
    engine = OpenAIEngine(api_key, model="gpt-4o-mini")
    assistant = Kani(engine, system_prompt=instructions,
                     chat_history=chat_history)
    response = await assistant.chat_round_str(message)
    return response


async def generate_response(history_json: list[dict], instructions: str, message: str) -> ChatMessage:
    chat_history = [ChatMessage.model_validate(chat) for chat in history_json]
    response = await _generate_response(chat_history, instructions, message)
    return response
