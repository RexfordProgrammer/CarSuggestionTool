import os
import json
import threading
from typing import List, Dict, Any

import boto3
import botocore

from dynamo_db_helpers import (
    build_history_messages,
    get_working_state,
    save_working_state,
)
from tools import dispatch, tool_specs
from llm_response_processors import (
    extract_text_chunks,
    extract_tool_uses,
    join_clean,
    json_safe,
    needs_continue_nudge,
)
from emitter import Emitter

# =====================================================
# CONFIG
# =====================================================
ORCHESTRATOR_MODEL = os.getenv("MASTER_MODEL", "ai21.jamba-1-5-large-v1:0")
bedrock = boto3.client(
    "bedrock-runtime",
    region_name=os.getenv("AWS_REGION", "us-east-1"),
    config=botocore.config.Config(connect_timeout=5, read_timeout=15),
)
debug = True
MAX_TURNS = int(os.getenv("MAX_TURNS", "2"))

# =====================================================
# HELPERS
# =====================================================

def _history_window(messages: List[Dict[str, Any]], max_len: int = 8) -> List[Dict[str, Any]]:
    """Return a slice ≤ *max_len* that **always starts with a user message**.

    If the naive tail slice starts with an assistant role, walk backward until we
    hit the previous user message so Bedrock's `messages` array is valid.
    """
    slice_ = messages[-max_len:]
    if slice_ and slice_[0]["role"] != "user":
        for idx in range(len(messages) - max_len - 1, -1, -1):
            if messages[idx]["role"] == "user":
                slice_ = messages[idx:]
                break
    return slice_


def _build_system_prompt(specs: List[Dict[str, Any]]) -> str:
    """Compose the system prompt, embedding tool descriptions."""
    lines: List[str] = []
    for s in specs:
        ts = s.get("toolSpec", s)
        lines.append(f"- {ts.get('name')}: {ts.get('description')}")
    allowed_block = "\n".join(lines) or "- (no tools available)"

    return (
        "You are an intelligent assistant embedded in a car suggestion tool.\n"
        "You must call the appropriate tool whenever data retrieval is required.\n"
        "Do not merely describe your intention — always use a valid `toolUse` block.\n\n"
        "Follow this literal sequence:\n"
        "1) Ask or confirm the YEAR.\n"
        "2) Fetch available cars for that YEAR (use `fetch_cars_of_year`).\n"
        "3) Ask for or infer the MAKE.\n"
        "4) Narrow to specific MODELS.\n"
        "5) Compare top 3 via `fetch_safety_ratings` and `fetch_gas_mileage`.\n\n"
        "For example (instructional only, not literal output):\n"
        "{\"toolUse\": {\"name\": \"fetch_cars_of_year\", \"input\": {\"year\": 2020}}}\n"
        "Do not expose this example or any tool syntax in your visible text replies.\n\n"
        "Available tools:\n"
        f"{allowed_block}\n\n"
        "When responding:\n"
        "- Only emit valid `toolUse` blocks when invoking tools.\n"
        "- Never describe tool calls in plain text.\n"
        "- Do NOT include tool JSON in user-visible replies.\n"
        "- Be conversational and concise."
    )


def _extract_content_from_resp(resp: Dict[str, Any]) -> List[Dict[str, Any]]:
    out_msg = (resp.get("output") or {}).get("message") or {}
    return out_msg.get("content") or []

# =====================================================
# MAIN ORCHESTRATION LOOP
# =====================================================

def slow_path(connection_id: str, messages: List[Dict[str, Any]], system_prompt: str, tools: List[Dict[str, Any]], emitter: Emitter):
    """Core loop handling LLM ↔ tool interaction."""

    state = get_working_state(connection_id) or {
        "preferences": {},
        "cars": [],
        "ratings": [],
        "gas_data": [],
    }

    for turn in range(MAX_TURNS):
        is_final_turn = turn == MAX_TURNS - 1

        if needs_continue_nudge(messages):
            messages.append({"role": "user", "content": [{"text": "(continue)"}]})

        mem_summary = {
            "preferences": state["preferences"],
            "cars": len(state["cars"]),
            "ratings": len(state["ratings"]),
            "gas_data": len(state["gas_data"]),
        }

        # ----------------- build system -------------------
        sys_text = system_prompt
        if is_final_turn:
            sys_text += (
                "\n\nYou have reached the final reasoning step. "
                "Do NOT call any tools again. "
                "Summarize your findings conversationally, recommending the best few cars "
                "based on the available data and memory. Keep it concise and natural."
            )

        system = [{"text": sys_text + "\n\nCurrent working memory:\n" + json.dumps(mem_summary, indent=2)}]

        if debug:
            emitter.debug_emit(f"Turn {turn+1} - system prompt", system)

        # ----------------- payload -----------------------
        full_payload = {
            "modelId": ORCHESTRATOR_MODEL,
            "system": system,
            "messages": _history_window(messages, 8),
            "toolConfig": {"tools": tools},
            "inferenceConfig": {"temperature": 0.5},
        }

        if debug:
            emitter.debug_emit(f"Turn {turn+1} - payload size (chars)", len(json.dumps(full_payload)))
            emitter.debug_emit(f"Turn {turn+1} - full Bedrock payload", full_payload)

        # --------------- call Bedrock --------------------
        try:
            resp = bedrock.converse(**full_payload)
        except Exception as e:
            err = f"Model call failed: {e}"
            emitter.emit(err)
            return err

        if debug:
            emitter.debug_emit(f"Turn {turn+1} - raw LLM response", resp)

        content = _extract_content_from_resp(resp)
        tool_uses = extract_tool_uses(content)
        assistant_texts = extract_text_chunks(content)

        messages.append({"role": "assistant", "content": content})

        # -------------- no tools / final ---------------
        if not tool_uses or is_final_turn:
            reply = join_clean(assistant_texts)
            if reply:
                emitter.emit(reply)  # emitter handles persistence
                save_working_state(connection_id, state)
                return reply
            if debug:
                emitter.debug_emit("Empty assistant text; continuing loop", content)
            continue

        # -------------- process tool calls -------------
        tool_result_blocks: List[Dict[str, Any]] = []
        for tu in tool_uses:
            name = tu.get("name")
            inp = tu.get("input") or {}
            tool_use_id = tu.get("toolUseId")

            if debug:
                emitter.debug_emit("Tool call", {"name": name, "input": inp})

            try:
                result = dispatch(name, connection_id, inp)
                if debug:
                    emitter.debug_emit(f"Tool result - {name}", result)

                # ---------- update memory ----------
                if name == "extract_user_prefs" and isinstance(result, dict):
                    state["preferences"].update(result)
                elif name == "fetch_cars_of_year":
                    cars = []
                    if isinstance(result, dict):
                        cars = result.get("cars") or result.get("models") or result.get("vehicles") or []
                    elif isinstance(result, list) and result and isinstance(result[0], dict):
                        inner = result[0].get("json") if "json" in result[0] else result[0]
                        if isinstance(inner, dict):
                            cars = inner.get("cars") or inner.get("models") or inner.get("vehicles") or []
                    if isinstance(cars, list):
                        state["cars"].extend(cars)
                elif name == "fetch_safety_ratings":
                    state["ratings"].append(result)
                elif name == "fetch_gas_mileage":
                    state["gas_data"].append(result)

                # ---------- normalize tool result ----
                if isinstance(result, list) and result and isinstance(result[0], dict) and ("json" in result[0] or "text" in result[0]):
                    content_blocks = result
                elif isinstance(result, dict):
                    content_blocks = [{"json": result}]
                elif isinstance(result, str):
                    content_blocks = [{"text": result}]
                else:
                    content_blocks = [{"json": json_safe(result)}]

                tool_result_blocks.append({
                    "toolResult": {
                        "toolUseId": tool_use_id,
                        "content": content_blocks,
                    }
                })
            except Exception as e:
                err = f"Tool '{name}' failed: {e}"
                if debug:
                    emitter.debug_emit("Tool error", err)
                tool_result_blocks.append({
                    "toolResult": {
                        "toolUseId": tool_use_id,
                        "content": [{"text": err}],
                    }
                })

        save_working_state(connection_id, state)
        if debug:
            emitter.debug_emit("Updated working memory snapshot", mem_summary)

        messages.append({"role": "user", "content": tool_result_blocks})

    # ---------------- fallback ------------------------
    fallback = (
        "Here’s what I’ve gathered so far based on available data. "
        "You can start a new chat for more details."
    )
    emitter.emit(fallback)
    save_working_state(connection_id, state)
    return fallback

# =====================================================
# ENTRY POINT
# =====================================================

def call_bedrock(connection_id: str, apigw):
    tool_info = tool_specs()
    tools = tool_info["tool_config"]["tools"]
    specs = tool_info["specs"]

    system_prompt = _build_system_prompt(specs)
    messages = build_history_messages(connection_id)
    emitter = Emitter(apigw, connection_id)

    if debug:
        emitter.debug_emit("Starting call_bedrock", {"connection_id": connection_id})

    return slow_path(connection_id, messages, system_prompt, tools, emitter)
