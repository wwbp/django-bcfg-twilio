from openai import OpenAI
from openai._compat import model_dump
client = OpenAI()

MODERATION_VALUES_FOR_BLOCKED = {
    "harassment": 0.5,
    "harassment/threatening": 0.1,
    "hate": 0.5,
    "hate/threatening": 0.1,
    "self-harm": 0.2,
    "self-harm/instructions": 0.5,
    "self-harm/intent": 0.7,
    "sexual": 0.5,
    "sexual/minors": 0.2,
    "violence": 0.7,
    "violence/graphic": 0.8,
}


def moderate_message(message: str) -> str:
    moderation_response = client.moderations.create(
        input=message, model="omni-moderation-latest"
    )
    category_scores = moderation_response.results[0].category_scores or {}

    category_score_items = model_dump(category_scores)

    blocked_str = ""
    for category, score in category_score_items.items():
        if score is None:
            continue
        if score > MODERATION_VALUES_FOR_BLOCKED.get(category, 1.0):
            blocked_str += f"({category}: {score})"
            break
    return blocked_str
