import os
import json
import boto3
from typing import List, Dict, Any
from dynamo_db_helpers import (
    get_session_messages,
    save_bot_response,
    get_working_state,
    save_working_state,
)
from tools import tool_specs, dispatch
from target_flags import get_target_flags

ORCHESTRATOR_MODEL = os.getenv("MASTER_MODEL", "ai21.jamba-1-5-large-v1:0")
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")


def _build_history_messages(connection_id: str) -> List[Dict[str, Any]]:
    """Fetch and format prior chat messages for Bedrock Converse."""
    raw = get_session_messages(connection_id) or []
    msgs = []
    for m in raw:
        role = m.get("role")
        content = m.get("content")
        if role in ("user", "assistant") and isinstance(content, str):
            msgs.append({"role": role, "content": [{"text": content}]})
    return msgs


def _build_system_prompt(base_prompt: str, specs: List[Dict[str, Any]]) -> str:
    """Injects allowed tool list and agentic instructions."""
    flags_str = ", ".join(f'"{f}"' for f in get_target_flags())
    allowed_lines = [f"- `{s.get('name')}`: {s.get('description')}" for s in specs]
    allowed_block = "\n".join(allowed_lines) or "- (no tools available)"

    return (
        f"{base_prompt}\n\n"
        "You are an autonomous car-recommendation assistant that may plan and execute several steps.\n"
        "You can reason and call tools over multiple rounds to gather all needed info before answering.\n"
        "Say 'DONE' when you have provided your final answer.\n\n"
        "Available tools:\n"
        f"{allowed_block}\n\n"
        "Guidance:\n"
        "- Use `fetch_user_preferences` to ANALYZE the conversation so far (not an API call). "
        f"Extract what the user has already mentioned about their desired car, such as {flags_str}, brand, budget, and body style.\n"
        "- Use `fetch_cars_of_year` to get available cars for a given year.\n"
        "- Use `fetch_safety_rating` for NHTSA safety ratings.\n"
        "- Use `fetch_gas_milage` for fuel economy.\n"
        "- After each tool call, re-evaluate what to do next.\n"
        "- Keep all replies concise and natural.\n"
        "- Refer to the working memory to avoid redundant actions.\n"
    )

def call_bedrock(connection_id: str, base_system_prompt: str, skip_tools: bool = False) -> str:
    """
    Hybrid orchestrator:
    - Fast single-shot path for simple prompts (no tools, low latency)
    - Agentic multi-turn mode for complex reasoning or when tools are needed
    - Optional 'skip_tools=True' flag to fully disable tool use
    """
    # === Build system and history ===
    specs = tool_specs() if not skip_tools else []
    tool_config = {"tools": [{"toolSpec": s} for s in specs]} if specs else None
    allowed_names = [s.get("name") for s in specs]

    system_prompt = _build_system_prompt(base_system_prompt, specs)
    messages = _build_history_messages(connection_id)

    # Ensure last message is user
    if not messages or messages[-1]["role"] != "user":
        messages.append({"role": "user", "content": [{"text": "(continue reasoning)"}]})

    # === Fast single-shot path ===
    # Criteria: short conversation, skip_tools=True, or user likely not asking for tool work
    if skip_tools or (len(messages) <= 2 and len(messages[-1]["content"][0]["text"]) < 60):
        print("[Fast Path] Running single-shot conversation (no tool orchestration).")
        resp = bedrock.converse(
            modelId=ORCHESTRATOR_MODEL,
            system=[{"text": base_system_prompt}],
            messages=messages,
            inferenceConfig={"temperature": 0.5},
        )
        out_msg = (resp.get("output") or {}).get("message") or {}
        content = out_msg.get("content") or []
        texts = [c.get("text") for c in content if "text" in c]
        reply = (texts[0] if texts else "(no output)").strip()
        save_bot_response(reply, connection_id)
        return reply

    # ===  Agentic mode with working memory ===
    state = get_working_state(connection_id) or {
        "preferences": {},
        "cars": [],
        "ratings": [],
        "gas_data": [],
    }

    MAX_TURNS = 5
    reply = "(no output)"

    for turn in range(MAX_TURNS):
        print(f"--- Agentic turn {turn+1}/{MAX_TURNS} ---")

        if not messages or messages[-1]["role"] != "user":
            messages.append({"role": "user", "content": [{"text": "(continue reasoning)"}]})

        system = [{
            "text": system_prompt
            + "\n\nCurrent working memory:\n"
            + json.dumps(state, indent=2)
        }]

        resp = bedrock.converse(
            modelId=ORCHESTRATOR_MODEL,
            system=system,
            messages=messages,
            toolConfig=tool_config if not skip_tools else None,
            inferenceConfig={"temperature": 0.5},
        )

        out_msg = (resp.get("output") or {}).get("message") or {}
        content = out_msg.get("content") or []
        tool_uses = [c.get("toolUse") for c in content if "toolUse" in c]

        # === Simple conversational reply ===
        if skip_tools or not tool_uses:
            texts = [c.get("text") for c in content if "text" in c]
            reply = (texts[0] if texts else "(no output)").strip()
            save_bot_response(reply, connection_id)
            save_working_state(connection_id, state)
            if "done" in reply.lower():
                print("[Agent] Declared DONE, ending loop.")
                break
            messages.append({"role": "assistant", "content": content})
            continue

        # === Tool execution ===
        messages.append({"role": "assistant", "content": content})
        tool_results_content: List[Dict[str, Any]] = []

        for tu in tool_uses:
            name = tu.get("name")
            use_id = tu.get("toolUseId")
            tool_input = tu.get("input") or {}
            print(f"[ToolUse] {name} (ID: {use_id}) Input: {json.dumps(tool_input)}")

            status = "success"
            try:
                if name not in allowed_names:
                    raise ValueError(f"Invalid tool '{name}'")
                result_content = dispatch(name, connection_id, tool_input)

                # Normalize and update memory
                if isinstance(result_content, dict):
                    result_json = result_content
                    result_content = [{"json": result_json}]
                elif isinstance(result_content, str):
                    result_json = {"text": result_content}
                    result_content = [{"text": result_content}]
                elif isinstance(result_content, list):
                    result_json = result_content[0].get("json", {}) if result_content else {}
                else:
                    result_json = {"raw": str(result_content)}
                    result_content = [{"text": str(result_content)}]

                if name == "fetch_user_preferences":
                    state["preferences"].update(result_json)
                elif name == "fetch_cars_of_year":
                    cars = result_json.get("cars") or result_json.get("models") or []
                    if isinstance(cars, list):
                        state["cars"].extend(cars)
                elif name == "fetch_safety_rating":
                    state["ratings"].append(result_json)
                elif name == "fetch_gas_milage":
                    state["gas_data"].append(result_json)

            except Exception as e:
                status = "error"
                result_content = [{"text": f"Tool '{name}' failed: {e}"}]

            tool_results_content.append({
                "toolResult": {
                    "toolUseId": use_id,
                    "status": status,
                    "content": result_content or [{"text": "(no content)"}],
                }
            })

        save_working_state(connection_id, state)
        messages.append({"role": "user", "content": tool_results_content})

    return reply
