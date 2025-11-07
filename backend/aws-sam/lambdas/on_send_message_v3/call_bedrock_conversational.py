import boto3
import json
from typing import List, Literal, Dict, Any, Optional
from pydantic import BaseModel, ValidationError

from target_flags import get_target_flags
from tools import tool_specs, dispatch

# Use env if set; default to us-east-1 + Jamba
ORCHESTRATOR_MODEL = "ai21.jamba-1-5-large-v1:0"
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


def _load_history_as_converse_messages(connection_id: str) -> List[Dict[str, Any]]:
    """Load prior messages from Dynamo and map to Bedrock Converse message format."""
    from dynamo_db_helpers import get_session_messages

    raw = get_session_messages(connection_id) or []
    messages: List[Dict[str, Any]] = []

    for m in raw:
        try:
            if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str):
                validated = ChatMessage(**m)
                messages.append({
                    "role": validated.role,
                    "content": [{"text": validated.content}],
                })
        except ValidationError:
            # Skip any malformed rows
            continue

    return messages


def _extract_text_and_tool_use(content: List[Dict[str, Any]]) -> tuple[str, Optional[Dict[str, Any]]]:
    """
    From a Bedrock 'message.content' list, extract concatenated text and the first toolUse (if any).
    Items may look like {'text': '...'} or {'toolUse': {...}}.
    """
    text_parts: List[str] = []
    first_tool_use: Optional[Dict[str, Any]] = None

    for item in content or []:
        if "text" in item and isinstance(item["text"], str):
            text_parts.append(item["text"])
        elif "toolUse" in item and first_tool_use is None:
            first_tool_use = item["toolUse"]

    return ("\n".join(text_parts).strip(), first_tool_use)


def get_conversational_response(connection_id: str) -> str:
    """
    Main orchestrator:
    - Builds system prompt
    - Calls Bedrock with toolConfig (native tool calls)
    - If toolUse is emitted, dispatch locally and return a final assistant message
    """
    # === System prompt ===
    flags_str = ", ".join(f'"{f}"' for f in get_target_flags())
    system_prompt = (
        "You are an intelligent assistant embedded in a car suggestion tool. "
        "Speak naturally with the user. You may call tools when needed. "
        f"When a user asks for car recommendations or wants to view vehicles, call the 'fetch_user_preferences' tool "
        f"to gather or confirm details such as {flags_str}, brand, budget, and body style. "
        "After tool results are provided, integrate them into a concise, friendly reply (2–3 sentences)."
    )

    system = [{"text": system_prompt}]
    messages = _load_history_as_converse_messages(connection_id)
    tools = [{"toolSpec": spec} for spec in tool_specs()]

    # === First call ===
    resp = bedrock.converse(
        modelId=ORCHESTRATOR_MODEL,
        system=system,
        messages=messages,
        toolConfig={"tools": tools},
    )

    content = (resp.get("output") or {}).get("message", {}).get("content", [])
    text_reply, tool_use = _extract_text_and_tool_use(content)

    # If the model already produced a normal text reply with no tool use, return it.
    if tool_use is None:
        return text_reply or "(no reply from model)"

    # === Execute the requested tool ===
    tool_name = tool_use.get("name")
    tool_input = tool_use.get("input") or {}
    tool_use_id = tool_use.get("toolUseId")

    try:
        result_content = dispatch(tool_name, connection_id, tool_input)
    except Exception as e:
        # Provide an error back to the model in case it wants to recover
        result_content = [{"text": f"Tool '{tool_name}' failed: {e}"}]

    # === Send toolResult and get final assistant text ===
    followup = bedrock.converse(
        modelId=ORCHESTRATOR_MODEL,
        system=system,
        messages=messages
        + [
            {"role": "assistant", "content": [{"toolUse": tool_use}]},
            {
                "role": "user",
                "content": [
                    {
                        "toolResult": {
                            "toolUseId": tool_use_id,
                            "content": result_content,
                        }
                    }
                ],
            },
        ],
    )

    f_content = (followup.get("output") or {}).get("message", {}).get("content", [])
    final_text, _ = _extract_text_and_tool_use(f_content)

    return final_text or "(no reply from model)"
