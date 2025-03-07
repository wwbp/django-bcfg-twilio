# chat/arbitrar.py
import asyncio
import json
from .models import StrategyPrompt
from .crud import load_detailed_transcript, save_chat_round_group
from .completion import chat_completion
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

    system_prompt = """
    You are an evaluation engine whose task is to determine whether a given strategy is applicable to the conversation based on the following inputs:

    **Your Task:**
    Analyze the conversation transcript and assess whether the Strategy Timing conditions are met. Be objective in your reasoning—only conclude that the strategy is applicable if the evidence is strong and the criteria are clearly satisfied. If there is any doubt or insufficient evidence, err on the side of caution.

    **Return Format:**
    Output your response in strict JSON format with exactly these keys:
    {
    "applicable": <true/false>, 
    "confidence": <a number between 0 and 1>, 
    "explanation": <brief explanation (less than 100 words)>
    }

    Do not include any additional commentary outside the JSON output. Evaluate based on the actual turns and active participation; do not rely solely on keywords. If unsure, return "applicable": false with a low confidence score.
    """

    # ** Context Dump **
    # 1. **Detailed Transcript:** A full transcript of a group conversation with multiple turns.
    # """ + f"2. **Strategy Timing Intelligence:** which relates to when the chatbot should respond. {strategy.when_prompt}" + """ + f"2.
    # 3. **Strategy Addressee Intelligence:** which relates to whom the chatbot should respond (e.g., a specific group, unspecified participants, or all participants) {strategy.when_prompt}" + """

    context_prompt = (
        f"1. **Detailed Transcript:** A full transcript of a group conversation with multiple turns.\n{transcript_text}\n\n"
        "--------------------------------\n\n"
        f"2. **Strategy Timing Intelligence:** which relates to when the chatbot should respond.\n {strategy.when_prompt}\n\n"
        "--------------------------------\n\n"
        f"3. **Strategy Addressee Intelligence:** which relates to whom the chatbot should respond (e.g., a specific group, unspecified participants, or all participants).\n {strategy.who_prompt}\n\n"
        "--------------------------------\n\n"
    )

    composite_prompt = context_prompt + system_prompt

    logging.info(
        f"Composite prompt for strategy {strategy.id}: {composite_prompt}")
    try:
        # Call the GPT completion function
        response = asyncio.run(chat_completion(composite_prompt))
        logging.info(
            f"Response from GPT for strategy {strategy.name}: {response}")

        # Attempt to parse the JSON output
        result = json.loads(response)

        # Check if required keys are in the JSON
        for key in ("applicable", "confidence", "explanation"):
            if key not in result:
                raise ValueError(f"Missing key in JSON response: {key}")

    except json.JSONDecodeError as e:
        logging.error(f"JSON decoding error: {e}")
        result = {
            "applicable": False,
            "confidence": 0.0,
            "explanation": "Failed to decode JSON response from GPT."
        }
    except Exception as e:
        logging.error(f"Error in strategy evaluation: {e}")
        result = {
            "applicable": False,
            "confidence": 0.0,
            "explanation": "An error occurred during strategy evaluation."
        }

    # Return tuple (is_applicable, detailed result)
    return result["applicable"], result


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
            f"Detailed Transcript:\n{transcript_text}\n\n"
            "--------------------------------\n\n"
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

        response = asyncio.run(chat_completion(instructions))
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
