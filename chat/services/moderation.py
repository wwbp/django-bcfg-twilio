from openai import OpenAI
from openai._compat import model_dump
from django.conf import settings


def moderate_message(message: str) -> str:
    moderation_response = OpenAI(api_key=settings.OPENAI_API_KEY).moderations.create(
        input=message, model="omni-moderation-latest"
    )
    category_scores = moderation_response.results[0].category_scores or {}
    category_score_items = model_dump(category_scores)

    blocked_str = ""
    for category, score in category_score_items.items():
        if score is None:
            continue
        if score > settings.MODERATION_VALUES_FOR_BLOCKED.get(category, 1.0):
            blocked_str += f"({category}: {score})"
            break
    return blocked_str
