import asyncio
from .completion import generate_response
from .crud import load_chat_prompt, save_chat_round_group, verify_update_database, load_chat_history_json, save_chat_round, verify_update_database_group
from .send import send_message_to_participant, send_message_to_participant_group


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
    history_json = load_chat_history_json(group_id)
    instructions = load_chat_prompt(data['context']['week_number'], group=True)
    response = asyncio.run(generate_response(
        history_json, instructions, data['message']))
    save_chat_round_group(
        group_id, data['sender_id'], data['message'], response)
    print(f"Generated group response for group {group_id}: {response}")
    return response
