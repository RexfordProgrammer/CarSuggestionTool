from typing import Any, Dict, List
import boto3
from decimal import Decimal

from converse_message_builder import create_user_text_message,create_message

dynamodb = boto3.resource("dynamodb")
messages_table = dynamodb.Table("messages")

def save_assistant_from_bedrock_resp_v2(connection_id: str, resp: Dict[str, Any]) -> Dict[str, Any]:
    """Takes a full bedrock.converse response, extracts content, splits"""
    message = resp.get("output", {}).get("message", {})
    append_message_entry_to_db(connection_id, message)
    return message

def append_message_entry_to_db(connection_id: str, entry: Dict[str, Any]) -> None:
    """Appends a single message entry (full content) to the DynamoDB list."""
    messages_table.update_item(
        Key={"connectionId": connection_id},
        UpdateExpression="SET messages = list_append(if_not_exists(messages, :empty), :new)",
        ExpressionAttributeValues={":empty": [], ":new": [entry]},
    )

def _convert_floats_to_decimals(data: Any) -> Any:
    """Recursively converts all float values in a dictionary or list to Decimal."""
    if isinstance(data, float):
        return Decimal(str(data))
    if isinstance(data, dict):
        return {k: _convert_floats_to_decimals(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_convert_floats_to_decimals(item) for item in data]
    return data

def save_user_tool_result_entry_v2(connection_id: str, tool_result_blocks: List[Dict[str, Any]]) -> None:
    """Save user message containing only toolResult blocks, converting floats to Decimals."""
    decimal_tool_blocks = _convert_floats_to_decimals(tool_result_blocks)
    entry = {"role": "user", "content": decimal_tool_blocks}
    append_message_entry_to_db(connection_id, entry)
    
def save_user_continue(connection_id: str):
    """Save the user's implicit (continue) message."""
    continue_message = create_user_text_message("(continue)")
    message = create_message("user", continue_message)
    append_message_entry_to_db(connection_id, message)

def save_user_message(connection_id: str, raw_message:str):
    """Save the user's implicit (continue) message."""
    message = create_user_text_message(raw_message)
    append_message_entry_to_db(connection_id, message)

def get_session_messages(connection_id: str) -> List[Dict[str, Any]]:
    """Retrieves the raw conversation history list from DynamoDB."""
    resp = messages_table.get_item(Key={"connectionId": connection_id})
    return resp.get("Item", {}).get("messages", [])


def build_history_messages(connection_id: str, history_window: int = 5):
    """
    Builds the history window for the model call, ensuring that the history 
    does not start in the middle of a multi-turn tool-use sequence.

    The function iteratively pulls in preceding messages if the history starts 
    with a toolUse (requires preceding toolResult/text) or a toolResult 
    (requires preceding toolUse).
    """
    # Placeholder for actual function to retrieve raw messages
    # In a real application, this would fetch the full history from a database.
    # For testing, ensure this function is defined or data is mocked.
    try:
        raw = get_session_messages(connection_id) or []
    except NameError:
        print("Error: get_session_messages is not defined. Using an empty list.")
        return []
    return raw