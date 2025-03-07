# chat/arbitrar.py
import asyncio
from .models import StrategyPrompt
from .crud import load_detailed_transcript, save_chat_round_group
from .completion import generate_response
from .send import send_message_to_participant_group

import logging

logger = logging.getLogger(__name__)


def evaluate_strategy_confidence(transcript_text: str, strategy: StrategyPrompt) -> float:
    """
    For a given strategy, build a composite prompt that includes:
      - The detailed transcript
      - The strategy's 'when' condition (trigger)
      - The strategy's 'what' instruction prompt

    Then call GPT to generate a confidence score (0-1) for the strategy.
    """
    composite_prompt = (
        f"Detailed Transcript:\n{transcript_text}\n\n"
        "--------------------------------\n\n"
        "Strategy Timing Intelligence, which relates to what the chatbot should respond.\n"
        f"Strategy When Condition: {strategy.when_prompt}\n\n"
        "Strategy Addressee Intelligence, which relates to whom the chatbot should respond (e.g., a specific group, unspecified participants, or all participants).\n"
        f"Strategy Who Criteria: {strategy.who_prompt}\n\n"
        "--------------------------------\n\n"
        "Your task is to determine if the above strategy is applicable to the conversation"
        "Return True or False based on the strategy's conditions and the conversation."
    )
    logging.info(
        f"Composite prompt for strategy {strategy.id}: {composite_prompt}")
    response = asyncio.run(generate_response([], composite_prompt, ""))
    is_applicable = True if "true" in response.lower() else False
    return is_applicable, response


def evaluate_strategies_with_gpt(transcript_text: str):
    """
    Evaluate all active strategies by using GPT to generate a confidence score
    for each strategy against the given transcript.

    Returns:
      A sorted list of tuples (strategy, score) for strategies scoring above the threshold.
    """
    logging.info("Evaluating strategies with GPT...")
    applicable = []
    active_strategies = StrategyPrompt.objects.filter(is_active=True)
    for strategy in active_strategies:
        is_applicable, response = evaluate_strategy_confidence(
            transcript_text, strategy)
        if is_applicable:
            applicable.append((strategy, response))
    return applicable


def process_arbitrar_layer(group_id: str):
    """
    Process the arbitrar layer for a group conversation.

    Steps:
      1. Compile the detailed transcript.
      2. For each active strategy, use GPT to get a confidence score.
      3. For those with a score above the threshold, generate a response
         using the strategy's 'what' prompt and the latest message.

    Returns a dictionary mapping each strategy's name to its generated response and confidence score.
    """
    logging.info(f"Processing arbitrar layer for group ID: {group_id}")
    transcript_text = load_detailed_transcript(group_id)
    applicable_strategies = evaluate_strategies_with_gpt(transcript_text)

    results = {}
    for strategy, response in applicable_strategies:
        instructions = (
            f"Strategy Intelligence, which relates to what the chatbot should respond.\n"
            f"Strategy What Prompt: {strategy.what_prompt}\n\n"
            "--------------------------------\n\n"
            "Strategy Timing Intelligence, which relates to what the chatbot should respond.\n"
            f"Strategy When Condition: {strategy.when_prompt}\n\n"
            "Strategy Addressee Intelligence, which relates to whom the chatbot should respond (e.g., a specific group, unspecified participants, or all participants).\n"
            f"Strategy Who Criteria: {strategy.who_prompt}\n\n"
            f"Results on if the strategy is applicable: {response}\n\n"
            "--------------------------------\n\n"
            "Your task is to generate next assistant response based on the strategy's intelligence instructions."
        )

        response = asyncio.run(generate_response(
            [], instructions, f"Detailed Transcript:\n{transcript_text}\n\n"))
        results[strategy.id] = response
    return results


async def send_strategy_responses(group_id: str, responses: dict):
    """
    Asynchronously send each generated strategy response to the group.

    Each message is prefixed with the strategy name.
    """
    logging.info(f"Sending strategy responses for group ID: {group_id}")
    # TODO priority order and evaluation

    for _, response in responses.items():
        await send_message_to_participant_group(group_id, response)
        save_chat_round_group(group_id, "assistant", "", response)
