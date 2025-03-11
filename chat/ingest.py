import asyncio
import logging

from .arbitrar import process_arbitrar_layer, send_multiple_responses
from .completion import generate_response
from .crud import load_chat_prompt, save_chat_round_group, verify_update_database, load_chat_history_json, save_chat_round, verify_update_database_group

logger = logging.getLogger(__name__)


def ingest_individual(user_id: str, data: dict):
    verify_update_database(user_id, data)
    history_json = load_chat_history_json(user_id)
    instructions = load_chat_prompt(data['context']['week_number'])
    response = asyncio.run(generate_response(
        history_json, instructions, data['message']))
    save_chat_round(user_id, data['message'], response)
    print(f"Generated response for participant {user_id}: {response}")
    return response


def ingest_group_sync(group_id: str, data: dict):
    print(
        f"Group message received for group {group_id} from sender {data['sender_id']}: {data['message']}")
    verify_update_database_group(group_id, data)
    # history_json = load_chat_history_json(group_id)
    # instructions = load_chat_prompt(data['context']['week_number'], group=True)
    # response = asyncio.run(generate_response(
    #     history_json, instructions, data['message']))
    save_chat_round_group(
        group_id, data['sender_id'], data['message'], "")
    strategy_responses = process_arbitrar_layer(group_id)
    logging.info(
        f"Generated responses for group {group_id}: {strategy_responses}")
    for _, response in strategy_responses.items():
        save_chat_round_group(group_id, None, "", response)
    asyncio.run(send_multiple_responses(group_id, strategy_responses))
    return strategy_responses
