# db_tools.py
from typing import Any, Dict, List
import boto3

from typecaster import dynamo_entry_from_resp  # <-- your conversions live here

# ==========================
# DynamoDB setup
# ==========================
dynamodb = boto3.resource("dynamodb")

# You can change this if your table name is different or env-based
MESSAGES_TABLE_NAME = "messages"
messages_table = dynamodb.Table(MESSAGES_TABLE_NAME)


def append_message_entry(connection_id: str, entry: Dict[str, Any]) -> None:
    """
    Low-level helper: append a single message entry to the `messages` list
    for a given connectionId.

    `entry` should look like:
        {
          "role": "assistant" | "user",
          "content": [ ... Bedrock content blocks ... ]
        }
    """
    messages_table.update_item(
        Key={"connectionId": connection_id},
        UpdateExpression="SET messages = list_append(if_not_exists(messages, :empty), :new)",
        ExpressionAttributeValues={
            ":empty": [],
            ":new": [entry],
        },
    )


def save_assistant_from_bedrock_resp(connection_id: str, resp: Dict[str, Any]) -> Dict[str, Any]:
    """
    Take a raw bedrock.converse `resp`, convert it into a Dynamo-friendly
    message entry using typecaster.dynamo_entry_from_resp, and append it
    to the `messages` array for this connection.

    This preserves native Bedrock content blocks, including any `toolUse`
    blocks, so later calls to converse can replay the full toolUse history.

    Returns the `entry` that was written to Dynamo.
    """
    # Let typecaster handle all the structural conversion
    entry = dynamo_entry_from_resp(resp)  # -> {"role": "...", "content": [ ... ]}

    # Persist to Dynamo
    append_message_entry(connection_id, entry)

    return entry


def save_user_bedrock_style(connection_id: str, blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Optional convenience: save a user message that's already in Bedrock
    block format (e.g. when you manually construct toolResult messages).

    Example `blocks`:
        [{"text": "2020"}]
        or
        [{"toolResult": {...}}, {"toolResult": {...}}]
    """
    if not isinstance(blocks, list):
        blocks = [blocks]

    entry: Dict[str, Any] = {
        "role": "user",
        "content": blocks,
    }

    append_message_entry(connection_id, entry)
    return entry
