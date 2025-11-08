import os
import json
import boto3
from typing import List, Dict, Any

from dynamo_db_helpers import get_session_messages, save_bot_response
from tools import tool_specs, dispatch
from target_flags import get_target_flags

ORCHESTRATOR_MODEL = os.getenv("MASTER_MODEL", "ai21.jamba-1-5-large-v1:0")
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")


def _build_history_messages(connection_id: str) -> List[Dict[str, Any]]:
    """Map prior conversation to Bedrock Converse message format."""
    raw = get_session_messages(connection_id) or []
    msgs: List[Dict[str, Any]] = []
    for m in raw:
        role = m.get("role")
        content = m.get("content")
        if role in ("user", "assistant") and isinstance(content, str):
            msgs.append({"role": role, "content": [{"text": content}]})
    return msgs


def _build_system_prompt(base_prompt: str, specs: List[Dict[str, Any]]) -> str:
    """Append allowed tools list and anti-hallucination guardrails."""
    flags_str = ", ".join(f'"{f}"' for f in get_target_flags())
    allowed_lines = []
    for s in specs:
        name = s.get("name", "<unnamed>")
        desc = s.get("description", "(no description)")
        allowed_lines.append(f"- `{name}`: {desc}")
    allowed_block = "\n".join(allowed_lines) if allowed_lines else "- (no tools available)"

    return (
        f"{base_prompt}\n\n"
        "You may only use the following tools. Do not invent new tool names:\n"
        f"{allowed_block}\n\n"
        "Guidance:\n"
        f"- Use `fetch_user_preferences` to determine or confirm attributes like {flags_str}, brand, budget, and body style.\n"
        "- Use `fetch_cars_of_year` to list available cars for a given year.\n"
        "- Use `fetch_safety_rating` to retrieve NHTSA safety ratings.\n"
        "- Use `fetch_gas_milage` to get fuel economy.\n"
        "- If none apply, continue without tools.\n"
        "Always integrate tool results into a concise, natural 2–3 sentence reply."
    )

def call_bedrock(connection_id: str, base_system_prompt: str) -> str:
    """Run the tool-aware Bedrock Converse flow with multi-tool handling and validation fixes."""
    # === Build Tool Configuration ===
    specs = tool_specs()
    tool_config = {"tools": [{"toolSpec": s} for s in specs]}
    allowed_names = [s.get("name") for s in specs]

    # === Build Prompts & History ===
    system_prompt = _build_system_prompt(base_system_prompt, specs)
    system = [{"text": system_prompt}]
    messages = _build_history_messages(connection_id)

    # === 1️⃣ First Converse Call ===
    resp = bedrock.converse(
        modelId=ORCHESTRATOR_MODEL,
        system=system,
        messages=messages,
        toolConfig=tool_config,
        inferenceConfig={"temperature": 0.5},
    )

    out_msg = (resp.get("output") or {}).get("message") or {}
    content = out_msg.get("content") or []
    tool_uses = [c.get("toolUse") for c in content if "toolUse" in c]

    # === If no tools requested → return normal text reply ===
    if not tool_uses:
        texts = [c.get("text") for c in content if "text" in c]
        reply = (texts[0] if texts else "(no output)").strip()
        save_bot_response(reply, connection_id)
        return reply

    # === 2️⃣ If tools requested → execute all tools ===
    messages_plus: List[Dict[str, Any]] = messages + [{"role": "assistant", "content": content}]
    tool_results_content: List[Dict[str, Any]] = []

    for tu in tool_uses:
        name = tu.get("name")
        use_id = tu.get("toolUseId")
        tool_input = tu.get("input") or {}

        print(f"[ToolUse] {name} (ID: {use_id}) Input: {json.dumps(tool_input)}")

        status = "success"
        try:
            if name not in allowed_names:
                status = "error"
                result_content = [{
                    "text": f"Invalid tool '{name}'. Allowed: {', '.join(allowed_names)}"
                }]
            else:
                # Dispatch the tool handler
                result_content = dispatch(name, connection_id, tool_input)
                if not isinstance(result_content, list):
                    # Wrap plain dicts or strings properly
                    if isinstance(result_content, dict):
                        result_content = [{"json": result_content}]
                    elif isinstance(result_content, str):
                        result_content = [{"text": result_content}]
                    else:
                        result_content = [{"text": str(result_content)}]
        except Exception as e:
            status = "error"
            result_content = [{"text": f"Tool '{name}' failed: {e}"}]

        # ✅ Collect this tool's result for the combined user message
        tool_results_content.append({
            "toolResult": {
                "toolUseId": use_id,
                "status": status,
                "content": result_content or [{"text": "(no content)"}],
            }
        })

    # === Append ONE combined user message with all toolResults ===
    messages_plus.append({
        "role": "user",
        "content": tool_results_content
    })

    # === 3️⃣ Second Converse Call (Final NL reply) ===
    print("[Follow-up] Sending tool results back to model...")
    resp2 = bedrock.converse(
        modelId=ORCHESTRATOR_MODEL,
        system=system,
        messages=messages_plus,
        toolConfig=tool_config,
        inferenceConfig={"temperature": 0.5},
    )

    out_msg2 = (resp2.get("output") or {}).get("message") or {}
    content2 = out_msg2.get("content") or []
    texts = [c.get("text") for c in content2 if "text" in c]
    reply = (texts[0] if texts else "(no output)").strip()

    save_bot_response(reply, connection_id)
    return reply

