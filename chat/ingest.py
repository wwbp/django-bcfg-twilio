import asyncio
from .completion import generate_response
from .crud import load_chat_prompt, verify_update_database, load_chat_history_json, save_chat_round
from .send import send_message_to_participant, send_message_to_participant_group


def ingest_individual(user_id: str, data: dict):
    # Update or create the user record
    verify_update_database(user_id, data)
    # Load existing chat history
    history_json = load_chat_history_json(user_id)
    # Create instructions from context
    instructions = load_chat_prompt(data['context']['week_number'])
    # Generate response using your async completion (bridged synchronously)
    response = asyncio.run(generate_response(
        history_json, instructions, data['message']))
    # Save the chat round
    save_chat_round(user_id, data['message'], response)
    # Send the message (bridged synchronously)
    asyncio.run(send_message_to_participant(user_id, response))
    print(f"Generated response for participant {user_id}: {response}")
    return response


def ingest_group_sync(group_id: str, data: dict):
    print(
        f"Group message received for group {group_id} from sender {data['sender_id']}: {data['message']}")
    # Update or create the group record (stubbed DB update)
    verify_update_database(group_id, data)
    # Build instructions from group context
    participant_names = ", ".join(
        [p['name'] for p in data['context'].get('participants', [])])
    instructions = f"Group chat from {data['context']['school_name']} with participants: {participant_names}"
    # Generate response; here we assume an empty chat history for groups
    response = asyncio.run(generate_response(
        [], instructions, data['message']))
    # Send the group message
    asyncio.run(send_message_to_participant_group(group_id, response))
    print(f"Generated group response for group {group_id}: {response}")
    return response
