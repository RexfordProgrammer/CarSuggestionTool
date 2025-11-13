from typing import Any, Dict, List
import boto3
import json

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("messages")
preferenceTable = dynamodb.Table("session-preferences")
memoryTable = dynamodb.Table("session-memory")

# ==========================
# Line-clipping utilities
# ==========================
_MAX_LINES = 10          # hard cap on lines per block
_MAX_LINE_CHARS = 200    # optional: cap width so lines don’t get huge

def _clip_text_lines(s: str, max_lines: int = _MAX_LINES, max_line_chars: int = _MAX_LINE_CHARS) -> str:
    """Clip a string to at most `max_lines`, truncating overly long lines."""
    lines = s.splitlines()
    clipped = []
    for line in lines[:max_lines]:
        if max_line_chars and len(line) > max_line_chars:
            clipped.append(line[:max_line_chars] + "…")
        else:
            clipped.append(line)
    if len(lines) > max_lines:
        clipped.append(f"... [truncated to {max_lines} lines]")
    return "\n".join(clipped)

def _normalize_to_blocks(content: Any) -> List[Dict[str, Any]]:
    """Normalize arbitrary content into Bedrock-style blocks."""
    if isinstance(content, list):
        return content
    if isinstance(content, str):
        return [{"text": content}]
    return [{"text": str(content)}]

def _clip_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Enforce ≤ max lines per block.
    - 'text' blocks: clip lines.
    - 'json' blocks: convert to pretty JSON string and clip lines (as 'text').
    - Other block types pass through unchanged (rare).
    """
    out: List[Dict[str, Any]] = []
    for b in blocks:
        if not isinstance(b, dict):
            out.append({"text": _clip_text_lines(str(b))})
            continue

        if "text" in b:
            out.append({"text": _clip_text_lines(str(b.get("text", "")))})
        elif "json" in b:
            try:
                pretty = json.dumps(b["json"], ensure_ascii=False, indent=2, default=str)
            except Exception:
                pretty = str(b["json"])
            out.append({"text": _clip_text_lines(pretty)})
        else:
            # Unknown block shape; stringify and clip
            out.append({"text": _clip_text_lines(json.dumps(b, ensure_ascii=False, default=str))})
    return out

def _clip_tool_result_blocks(tool_result_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    For toolResult messages, clip each inner content block to ≤ max lines.
    Converts json blocks to text previews to enforce line limits.
    """
    clipped: List[Dict[str, Any]] = []
    for item in tool_result_blocks or []:
        if not isinstance(item, dict) or "toolResult" not in item:
            # Defensive: if malformed, stringify and clip
            clipped.append({"toolResult": {"toolUseId": "unknown", "content": [{"text": _clip_text_lines(str(item))}]}})
            continue
        tr = item["toolResult"] or {}
        use_id = tr.get("toolUseId", "unknown")
        content_blocks = tr.get("content", [])
        content_blocks = _clip_blocks(_normalize_to_blocks(content_blocks))
        clipped.append({"toolResult": {"toolUseId": use_id, "content": content_blocks}})
    return clipped

# ==========================
# Session transcript
# ==========================
def get_session_messages(connection_id):
    """Return a list of messages for a given WebSocket connection."""
    response = table.get_item(Key={"connectionId": connection_id})
    item = response.get("Item")
    return item.get("messages", []) if item else []

def save_user_message(usermessage, connection_id):
    """Append a user message to the session's message list (Bedrock format), clipped to ≤10 lines per block."""
    blocks = _normalize_to_blocks(usermessage)
    blocks = _clip_blocks(blocks)
    entry = {"role": "user", "content": blocks}
    table.update_item(
        Key={"connectionId": connection_id},
        UpdateExpression="SET messages = list_append(if_not_exists(messages, :empty), :new)",
        ExpressionAttributeValues={":empty": [], ":new": [entry]},
    )

def save_bot_response(botmessage, connection_id):
    """Append an assistant message to the session's message list, clipped to ≤10 lines per block."""
    blocks = _normalize_to_blocks(botmessage)
    blocks = _clip_blocks(blocks)
    entry = {"role": "assistant", "content": blocks}
    table.update_item(
        Key={"connectionId": connection_id},
        UpdateExpression="SET messages = list_append(if_not_exists(messages, :empty), :new)",
        ExpressionAttributeValues={":empty": [], ":new": [entry]},
    )

def save_user_continue(connection_id):
    """Append a (continue) message in Bedrock format (already single-line)."""
    entry = {"role": "user", "content": [{"text": "(continue)"}]}
    table.update_item(
        Key={"connectionId": connection_id},
        UpdateExpression="SET messages = list_append(if_not_exists(messages, :empty), :new)",
        ExpressionAttributeValues={":empty": [], ":new": [entry]},
    )

def save_user_tool_result_message(connection_id: str, tool_result_blocks: list) -> None:
    """
    Append a Bedrock-compliant toolResult message, with each inner content block clipped to ≤10 lines.
    """
    clipped_tool_results = _clip_tool_result_blocks(tool_result_blocks)
    entry = {"role": "user", "content": clipped_tool_results}
    table.update_item(
        Key={"connectionId": connection_id},
        UpdateExpression="SET messages = list_append(if_not_exists(messages, :empty), :new)",
        ExpressionAttributeValues={":empty": [], ":new": [entry]},
    )

# ==========================
# History rebuild (unchanged)
# ==========================
def build_history_messages(connection_id: str) -> List[Dict[str, Any]]:
    """Reconstruct messages into valid Bedrock format from storage."""
    raw = get_session_messages(connection_id) or []
    msgs: List[Dict[str, Any]] = []
    for m in raw:
        role = m.get("role")
        content = m.get("content")
        if role not in ("user", "assistant"):
            continue
        if isinstance(content, list):
            msgs.append({"role": role, "content": content})
        elif isinstance(content, str):
            msgs.append({"role": role, "content": [{"text": content}]})
        else:
            msgs.append({"role": role, "content": [{"text": str(content)}]})
    return msgs

def get_tool_responses(
    connection_id: str,
    overall_max_chars: int = 12000,
    per_response_max_chars: int = 800
) -> str:
    try:
        res = table.get_item(Key={"connectionId": connection_id})
        item = res.get("Item", {}) or {}
        responses = item.get("tool_responses", []) or []
    except Exception as e:
        return f"(error loading tool responses: {e})"

    if not responses:
        return "(no tool responses)"

    lines: List[str] = []
    total_len = 0
    for idx, r in enumerate(responses, start=1):
        tool_name = str(r.get("tool", "unknown"))
        payload = r.get("result")
        try:
            if isinstance(payload, (dict, list)):
                payload_str = json.dumps(payload, ensure_ascii=False, default=str)
            else:
                payload_str = str(payload)
        except Exception:
            payload_str = str(payload)

        if len(payload_str) > per_response_max_chars:
            payload_str = payload_str[:per_response_max_chars] + " ... [truncated]"

        block = f"[{idx}] {tool_name}: {payload_str}"
        if total_len + len(block) + 1 > overall_max_chars:
            lines.append("... [overall tool responses truncated]")
            break

        lines.append(block)
        total_len += len(block) + 1

    return "\n".join(lines)
