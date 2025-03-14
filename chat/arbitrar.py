import asyncio
import json
import logging
from .models import StrategyPrompt
from .crud import load_detailed_transcript
from .completion import chat_completion
from .send import send_message_to_participant_group

logger = logging.getLogger(__name__)

# TODO: controllable variable pipe through db
CONFIDENCE_THRESHOLD = 0.5


def build_strategy_evaluation_prompt(transcript_text: str, strategy: StrategyPrompt) -> str:
    system_prompt = """
        You are an evaluation engine tasked with determining the applicability of a given strategy to the conversation.
        Analyze the transcript and assess the strength of evidence supporting the strategy.
        Return your response in strict JSON format with exactly these keys:
        {
            "confidence": <a number between 0 and 1>,
            "explanation": <brief explanation (less than 100 words)>
        }
        Do not include any additional commentary.
    """
    context_prompt = (
        f"Detailed Transcript:\n{transcript_text}\n\n"
        "--------------------------------\n\n"
        f"Strategy Timing Intelligence:\n{strategy.when_prompt}\n\n"
        "--------------------------------\n\n"
        f"Strategy Addressee Intelligence:\n{strategy.who_prompt}\n\n"
    )
    return system_prompt + context_prompt


def evaluate_single_strategy(transcript_text: str, strategy: StrategyPrompt) -> dict:
    composite_prompt = build_strategy_evaluation_prompt(
        transcript_text, strategy)
    logger.info(
        f"Composite prompt for strategy {strategy.id}: {composite_prompt}")
    try:
        response = asyncio.run(chat_completion(composite_prompt))
        logger.info(
            f"Response from GPT for strategy {strategy.name}: {response}")
        result = json.loads(response)
        for key in ("confidence", "explanation"):
            if key not in result:
                raise ValueError(f"Missing key in JSON response: {key}")
    except json.JSONDecodeError as e:
        logger.error(f"JSON decoding error: {e}")
        result = {"confidence": 0.0,
                  "explanation": "Failed to decode JSON response from GPT."}
    except Exception as e:
        logger.error(f"Error in strategy evaluation: {e}")
        result = {"confidence": 0.0,
                  "explanation": "An error occurred during strategy evaluation."}
    return result


def evaluate_all_strategies(transcript_text: str):
    logger.info("Evaluating strategies with GPT...")
    applicable = []
    active_strategies = StrategyPrompt.objects.filter(is_active=True)
    for strategy in active_strategies:
        result = evaluate_single_strategy(transcript_text, strategy)
        if result["confidence"] > CONFIDENCE_THRESHOLD:
            applicable.append((strategy, result))
    return applicable


def build_response_generation_prompt(transcript_text: str, strategy: StrategyPrompt, evaluation_result: dict) -> str:
    prompt = (
        f"Detailed Transcript:\n{transcript_text}\n\n"
        "--------------------------------\n\n"
        f"Strategy What Prompt:\n{strategy.what_prompt}\n\n"
        "--------------------------------\n\n"
        f"Strategy Timing Intelligence:\n{strategy.when_prompt}\n\n"
        "--------------------------------\n\n"
        f"Strategy Addressee Intelligence:\n{strategy.who_prompt}\n\n"
        f"Evaluation Result:\n{evaluation_result}\n\n"
        "Your task is to generate the next assistant response based on the above strategy."
    )
    return prompt


def generate_response_for_strategy(transcript_text: str, strategy: StrategyPrompt, evaluation_result: dict) -> str:
    prompt = build_response_generation_prompt(
        transcript_text, strategy, evaluation_result)
    logger.info(
        f"Response generation prompt for strategy {strategy.id}: {prompt}")
    #TODO generate response from kani to have built in moderation and 320 charac limiter
    response = asyncio.run(chat_completion(prompt))
    return response


def generate_all_strategy_responses(transcript_text: str, applicable_strategies: list):
    results = {}
    for strategy, evaluation_result in applicable_strategies:
        response = generate_response_for_strategy(
            transcript_text, strategy, evaluation_result)
        results[strategy.id] = response
    return results


def process_arbitrar_layer(group_id: str):
    logger.info(f"Processing arbitrar layer for group ID: {group_id}")
    transcript_text = load_detailed_transcript(group_id)
    applicable_strategies = evaluate_all_strategies(transcript_text)
    responses = generate_all_strategy_responses(
        transcript_text, applicable_strategies)
    return responses


async def send_multiple_responses(group_id: str, responses: list[str]):
    logger.info(f"Sending strategy responses for group ID: {group_id}")
    # TODO: add priority ordering if needed
    for response in responses:
        await send_message_to_participant_group(group_id, response)
