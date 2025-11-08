import boto3
import json
from typing import List, Literal, Dict, Any, Optional
from pydantic import BaseModel, ValidationError

from target_flags import get_target_flags
from tools import tool_specs, dispatch

# === Configuration ===
ORCHESTRATOR_MODEL = "ai21.jamba-1-5-large-v1:0"
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")


# === Message Model ===
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


# === Helpers ===
def _load_history_as_converse_messages(connection_id: str) -> List[Dict[str, Any]]:
    """Load prior messages from Dynamo and map to Bedrock Converse format."""
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
            continue

    return messages


def _extract_text_and_tool_use(content: List[Dict[str, Any]]) -> tuple[str, Optional[Dict[str, Any]]]:
    """Extract text and first toolUse (if any) from Bedrock message content."""
    text_parts: List[str] = []
    first_tool_use: Optional[Dict[str, Any]] = None

    for item in content or []:
        if "text" in item and isinstance(item["text"], str):
            text_parts.append(item["text"])
        elif "toolUse" in item and first_tool_use is None:
            first_tool_use = item["toolUse"]

    return ("\n".join(text_parts).strip(), first_tool_use)


# === Core ===
def get_conversational_response(connection_id: str) -> str:
    """
    Main orchestrator:
    - Builds system prompt with explicit allowed tools
    - Calls Bedrock with toolConfig (native tool calls)
    - Executes tool requests via dispatch
    """
    # Build explicit list of allowed tools
    specs = tool_specs()
    allowed_tools = [spec["name"] for spec in specs]
    allowed_tool_text = "\n".join(
        f"- `{spec['name']}`: {spec.get('description','(no description)')}"
        for spec in specs
    )

    # === System prompt ===
    flags_str = ", ".join(f'"{f}"' for f in get_target_flags())
    system_prompt = (
        "You are an intelligent assistant embedded in a car suggestion tool.\n"
        "You may only call the tools listed below — never invent new tool names.\n"
        f"{allowed_tool_text}\n\n"
        "Guidance:\n"
        f"- Use `fetch_user_preferences` to determine or confirm attributes like {flags_str}, brand, budget, or body style.\n"
        "- Use `fetch_cars_of_year` to list available cars for a given year.\n"
        "- Use `fetch_safety_rating` to retrieve NHTSA safety ratings.\n"
        "- Use `fetch_gas_milage` to get fuel economy info.\n"
        "- If none of these apply, continue the conversation without using a tool.\n"
        "Never fabricate tools such as 'get_truck_options' or 'lookup_vehicle_specs'.\n"
        "Respond conversationally and integrate tool results into natural 2–3 sentence replies."
    )

    system = [{"text": system_prompt}]
    messages = _load_history_as_converse_messages(connection_id)
    tools = [{"toolSpec": spec} for spec in specs]

    # === First call ===
    resp = bedrock.converse(
        modelId=ORCHESTRATOR_MODEL,
        system=system,
        messages=messages,
        toolConfig={"tools": tools},
    )

    content = (resp.get("output") or {}).get("message", {}).get("content", [])
    text_reply, tool_use = _extract_text_and_tool_use(content)

    # === No tool use → return normal message ===
    if tool_use is None:
        return text_reply or "(no reply from model)"

    # === Execute tool ===
    tool_name = tool_use.get("name")
    tool_input = tool_use.get("input") or {}
    tool_use_id = tool_use.get("toolUseId")

    try:
        # Validate that the tool name is allowed
        if tool_name not in allowed_tools:
            result_content = [{"text": f"Invalid tool '{tool_name}'. Allowed tools: {', '.join(allowed_tools)}"}]
        else:
            result_content = dispatch(tool_name, connection_id, tool_input)
    except Exception as e:
        result_content = [{"text": f"Tool '{tool_name}' failed: {e}"}]

    # === Follow-up call with toolResult ===
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
