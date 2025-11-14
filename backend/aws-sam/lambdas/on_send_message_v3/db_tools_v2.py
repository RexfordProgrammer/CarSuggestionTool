''' Refactored DB_Tools to use pydantic'''
from decimal import Decimal
from typing import Any, List
import boto3
from pydantic import ValidationError

from pydantic_models import ToolResultContentBlock

from converse_response_pydantic import (
    ConverseResponse,
Message,
    TextContentBlock,
)

# --- DynamoDB Setup ---
dynamodb = boto3.resource("dynamodb")
messages_table = dynamodb.Table("messages")

def _convert_floats_to_decimals(data: Any) -> Any:
    """Recursively converts all float values in a dictionary or list to Decimal."""
    if isinstance(data, float):
        # Convert float to string first to avoid precision loss
        return Decimal(str(data))
    if isinstance(data, dict):
        return {k: _convert_floats_to_decimals(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_convert_floats_to_decimals(item) for item in data]
    return data

def append_message_entry_to_db(connection_id: str, message: Message) -> None:
    """
    Appends a single Pydantic Message object to the DynamoDB list.
    """
    message_dict = message.model_dump(mode='json')    
    decimal_message = _convert_floats_to_decimals(message_dict)
    try:
        messages_table.update_item(
            Key={"connectionId": connection_id},
            UpdateExpression="SET messages = list_append(if_not_exists(messages, :empty), :new)",
            ExpressionAttributeValues={":empty": [], ":new": [decimal_message]},
        )
    except Exception as e:
        print(f"Error appending message to DB for {connection_id}: {e}")

def save_assistant_message(connection_id: str, resp: ConverseResponse):
    """
    Takes a full bedrock.converse response object, extracts the
    assistant's Message, and saves it to the database.
    """
    assistant_message = resp.output.message
    append_message_entry_to_db(connection_id, assistant_message)

def save_user_tool_results(connection_id: str, tool_result_blocks: ToolResultContentBlock) -> None:
    """
    Saves a user message containing one or more toolResult blocks.
    The input is a list of raw tool result block dictionaries.
    """
    try:
        content_blocks = [
            ToolResultContentBlock.model_validate(block) 
            for block in tool_result_blocks
        ]
        message = Message(role="user", content=content_blocks)
        append_message_entry_to_db(connection_id, message)
    except ValidationError as e:
        print(f"Validation error saving tool results for {connection_id}: {e}")

def save_user_message(connection_id: str, raw_message: str):
    """Saves a user's text message to the database."""
    content_block = TextContentBlock(text=raw_message)
    message = Message(role="user", content=[content_block])
    append_message_entry_to_db(connection_id, message)

def save_user_continue(connection_id: str):
    """Save the user's implicit (continue) message."""
    save_user_message(connection_id, "(continue)")


def get_session_messages(connection_id: str) -> List[Message]:
    """
    Retrieves the conversation history from DynamoDB
    and parses it into a list of Message objects.
    """
    try:
        resp = messages_table.get_item(Key={"connectionId": connection_id})
        raw_messages: List[dict] = resp.get("Item", {}).get("messages", [])

        if not raw_messages:
            return []

        validated_messages = [Message.model_validate(msg) for msg in raw_messages]
        return validated_messages

    except ValidationError as e:
        print(f"Data validation error for {connection_id}: {e}")
        return []
    except Exception as e:
        print(f"Error retrieving session messages for {connection_id}: {e}")
        return []

def build_history_messages(connection_id: str) -> List[Message]:
    """
    Builds the Pydantic Message history list for the model call.
    (This function was already correct as it just calls get_session_messages)
    """
    try:
        messages = get_session_messages(connection_id) or []
        return messages
    except Exception as e:
        print(f"Error building history for {connection_id}: {e}")
        return []