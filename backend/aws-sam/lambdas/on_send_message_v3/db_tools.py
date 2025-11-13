from typing import Any, Dict, List
import boto3
import json

# Assuming these are defined elsewhere and accessible
from bedrock_converse_handlers import (split_mixed_assistant, normalize_bedrock_blocks)

# ==========================
# DynamoDB setup
# ==========================
# Instantiate DynamoDB client (uses default AWS configuration)
dynamodb = boto3.resource("dynamodb")
messages_table = dynamodb.Table("messages")

# Configuration for message clipping
_MAX_LINES = 10
_MAX_LINE_CHARS = 200

# ==========================
# Line-clipping helpers (Unchanged)
# ==========================
def _clip_text_lines(s: str) -> str:
    lines = s.splitlines()
    clipped = []

    for line in lines[:_MAX_LINES]:
        if len(line) > _MAX_LINE_CHARS:
            clipped.append(line[:_MAX_LINE_CHARS] + "…")
        else:
            clipped.append(line)

    if len(lines) > _MAX_LINES:
        clipped.append(f"... [truncated to {_MAX_LINES} lines]")

    return "\n".join(clipped)


def _clip_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for b in blocks:
        if not isinstance(b, dict):
            out.append({"text": _clip_text_lines(str(b))})
            continue

        # Keep tool blocks intact for database storage, but clip their text/json content
        if "text" in b:
            out.append({"text": _clip_text_lines(str(b["text"]))})

        elif isinstance(b.get("json"), (dict, list)):
            pretty = json.dumps(b["json"], ensure_ascii=False, indent=2)
            out.append({"text": _clip_text_lines(pretty)})

        elif "toolUse" in b or "toolResult" in b or "toolRequest" in b:
            # We don't clip tool block content itself here, just ensure it's passed through
            out.append(b)

        else:
            out.append({"text": _clip_text_lines(json.dumps(b))})
            
    return out


# ==========================
# DynamoDB helpers (Unchanged)
# ==========================
def append_message_entry(connection_id: str, entry: Dict[str, Any]) -> None:
    """Appends a single message entry (full content) to the DynamoDB list."""
    messages_table.update_item(
        Key={"connectionId": connection_id},
        UpdateExpression="SET messages = list_append(if_not_exists(messages, :empty), :new)",
        ExpressionAttributeValues={":empty": [], ":new": [entry]},
    )

# ==========================
# Assistant responses (Unchanged)
# ==========================
def save_assistant_from_bedrock_resp(connection_id: str, resp: Dict[str, Any]) -> Dict[str, Any]:
    """
    Takes a full bedrock.converse response, extracts content, splits mixed assistant
    messages (text and tool blocks), and stores each individually. Returns the last saved entry.
    """
    message = resp.get("output", {}).get("message", {})
    entries = split_mixed_assistant(message)

    for e in entries:
        append_message_entry(connection_id, e)

    return entries[-1]

# ==========================
# User message saving (Unchanged)
# ==========================
def save_user_message(usermessage: Any, connection_id: str):
    """Save a simple user text message."""
    blocks = normalize_bedrock_blocks(usermessage)
    blocks = _clip_blocks(blocks) # Clips text only, keeps tool blocks if they exist
    entry = {"role": "user", "content": blocks}
    append_message_entry(connection_id, entry)


def save_bot_response(botmessage: Any, connection_id: str):
    """Save a simple assistant text message (non-tool)."""
    blocks = normalize_bedrock_blocks(botmessage)
    blocks = _clip_blocks(blocks)
    entry = {"role": "assistant", "content": blocks}
    append_message_entry(connection_id, entry)


def save_user_continue(connection_id: str):
    """Save the user's implicit (continue) message."""
    entry = {"role": "user", "content": [{"text": "(continue)"}]}
    append_message_entry(connection_id, entry)
    
def save_user_tool_result_entry(connection_id: str, tool_result_blocks: List[Dict[str, Any]]) -> None:
    """Save user message containing only toolResult blocks."""
    entry = {"role": "user", "content": tool_result_blocks}
    append_message_entry(connection_id, entry)

# ==========================
# Tool Block Filtering (NEW)
# ==========================
def _strip_tool_blocks_from_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """
    Removes tool-related content blocks from a message, preserving only text and 
    other non-tool blocks.
    """
    if not isinstance(message.get("content"), list):
        return message

    def is_tool_block(block):
        # Checks for the keys specific to tool calling in the content block
        return "toolUse" in block or "toolResult" in block or "toolRequest" in block

    # Filter out any blocks that are toolUse, toolResult, or toolRequest
    text_only_content = [
        block for block in message["content"] if not is_tool_block(block)
    ]
    
    # Create a new message with only the text content
    new_message = message.copy()
    new_message["content"] = text_only_content
    return new_message


# ==========================
# Read message history (Modified)
# ==========================
def get_session_messages(connection_id: str) -> List[Dict[str, Any]]:
    """Retrieves the raw conversation history list from DynamoDB."""
    resp = messages_table.get_item(Key={"connectionId": connection_id})
    return resp.get("Item", {}).get("messages", [])


def build_history_messages(connection_id: str) -> List[Dict[str, Any]]:
    """
    Builds the conversation history for the Bedrock API call.
    Critically, it strips out all tool-related blocks to reduce context size 
    and prevent validation errors.
    """
    raw = get_session_messages(connection_id) or []
    out = []

    for m in raw:
        role = m.get("role")
        
        if role not in ("user", "assistant"):
            continue

        # 1. Strip tool blocks
        cleaned_message = _strip_tool_blocks_from_message(m)
        content = cleaned_message.get("content")

        # 2. Skip messages that are empty after stripping (e.g., a user-only tool result turn)
        if not content:
            continue

        # 3. Append the text-only message to the history
        out.append({"role": role, "content": content})

    return out