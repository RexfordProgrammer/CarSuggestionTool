import os
import json
from typing import List, Dict, Any

import boto3
from dynamo_db_helpers import (
    build_history_messages,
    get_working_state,
    save_bot_response,
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
bedrock = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
debug = True

# =====================================================
# DEBUG EMIT (not persisted)
# =====================================================
def _emit_debug(emitter: Emitter, label: str, data: Any):
    if not debug:
        return
    try:
        text = json.dumps(data, indent=2, default=str)
    except Exception:
        text = str(data)
    preview = text[:1800] + ("..." if len(text) > 1800 else "")
    emitter.emit(f"[DEBUG] {label}:\n{preview}")

# =====================================================
# SYSTEM PROMPT
# =====================================================
def _build_system_prompt(specs: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for s in specs:
        ts = s.get("toolSpec", s)
        lines.append(f"- {ts.get('name')}: {ts.get('description')}")
    allowed_block = "\n".join(lines) or "- (no tools available)"

    return (
        "You are an intelligent assistant embedded in a car suggestion tool. "
        "You may call tools to retrieve data, but only emit valid `toolUse` blocks when needed.\n\n"
        "Follow this literal sequence:\n"
        "1) Ask or confirm the YEAR.\n"
        "2) Fetch available cars for that YEAR (use `fetch_cars_of_year`).\n"
        "3) Ask for or infer the MAKE.\n"
        "4) Narrow to specific MODELS.\n"
        "5) Compare top 3 via `fetch_safety_ratings` and `fetch_gas_mileage`.\n\n"
        "Available tools:\n"
        f"{allowed_block}\n\n"
        "When responding:\n"
        "- Do NOT expose tool names or JSON in text replies.\n"
        "- Use `toolUse` content blocks to call tools.\n"
        "- Be conversational and concise."
    )

# =====================================================
# RESPONSE EXTRACTION
# =====================================================
def _extract_content_from_resp(resp: Dict[str, Any]) -> List[Dict[str, Any]]:
    out_msg = (resp.get("output") or {}).get("message") or {}
    return out_msg.get("content") or []

# =====================================================
# MAIN FLOW
# =====================================================
def slow_path(connection_id, messages, system_prompt, tools, emitter):
    """
    - If the model returns text → emit it and return.
    - If the model returns toolUse(s) → run tools and send back a *single* user turn
      that contains only toolResult blocks (no normal text in that same message).
    """
    state = get_working_state(connection_id) or {
        "preferences": {},
        "cars": [],
        "ratings": [],
        "gas_data": [],
    }

    for turn in range(5):
        if needs_continue_nudge(messages):
            messages.append({"role": "user", "content": [{"text": "(continue)"}]})

        # Compact memory summary (counts only) BEFORE the turn
        pre_mem_summary = {
            "preferences": state.get("preferences"),
            "cars": len(state.get("cars", [])),
            "ratings": len(state.get("ratings", [])),
            "gas_data": len(state.get("gas_data", [])),
        }

        system = [{
            "text": system_prompt
                    + "\n\nCurrent working memory:\n"
                    + json.dumps(pre_mem_summary, indent=2)
        }]

        _emit_debug(emitter, f"Turn {turn+1} - system prompt", system_prompt)

        try:
            resp = bedrock.converse(
                modelId=ORCHESTRATOR_MODEL,
                system=system,
                messages=messages,
                toolConfig={"tools": tools},
                inferenceConfig={"temperature": 0.5},
            )
        except Exception as e:
            err = f"Model call failed: {e}"
            emitter.emit(err)
            return err

        _emit_debug(emitter, f"Turn {turn+1} - raw LLM response", resp)

        content = _extract_content_from_resp(resp)
        tool_uses = extract_tool_uses(content)
        assistant_texts = extract_text_chunks(content)

        # Record assistant output in history
        messages.append({"role": "assistant", "content": content})

        # === NO TOOLS: emit normal reply ===
        if not tool_uses:
            reply = join_clean(assistant_texts)
            if reply:
                emitter.emit(reply)
                # Persist only final user-visible text here (not debug)
                try:
                    save_bot_response(reply, connection_id)
                except Exception as e:
                    print(f"⚠️ save_bot_response failed (continuing): {e}")
                save_working_state(connection_id, state)
                return reply

            _emit_debug(emitter, "Empty assistant text; continuing loop", content)
            continue

        # === Handle tool calls ===
        tool_result_blocks: List[Dict[str, Any]] = []

        for tu in tool_uses:
            name = tu.get("name")
            inp = tu.get("input") or {}
            tool_use_id = tu.get("toolUseId")
            _emit_debug(emitter, "Tool call", {"name": name, "input": inp})

            try:
                result = dispatch(name, connection_id, inp)
                _emit_debug(emitter, f"Tool result - {name}", result)

                # Update working memory
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

                # Normalize result into Bedrock content blocks
                if isinstance(result, list) and result and isinstance(result[0], dict) and (
                    "json" in result[0] or "text" in result[0]
                ):
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
                err_text = f"Tool '{name}' failed: {e}"
                _emit_debug(emitter, "Tool error", err_text)
                tool_result_blocks.append({
                    "toolResult": {
                        "toolUseId": tool_use_id,
                        "content": [{"text": err_text}],
                    }
                })

        # Save state and log the *post*-update snapshot
        save_working_state(connection_id, state)
        post_mem_summary = {
            "preferences": state.get("preferences"),
            "cars": len(state.get("cars", [])),
            "ratings": len(state.get("ratings", [])),
            "gas_data": len(state.get("gas_data", [])),
        }
        _emit_debug(emitter, "Updated working memory snapshot", post_mem_summary)

        # ✅ Feed tool results back as a single user turn that contains ONLY toolResult blocks
        messages.append({
            "role": "user",
            "content": tool_result_blocks
        })

    # Fallback
    fallback = "Done."
    emitter.emit(fallback)
    try:
        save_bot_response(fallback, connection_id)
    except Exception as e:
        print(f"⚠️ save_bot_response failed (continuing): {e}")
    return fallback

# =====================================================
# ENTRY POINT
# =====================================================
def call_bedrock(connection_id: str, apigw) -> str:
    tool_info = tool_specs()
    tools = tool_info["tool_config"]["tools"]  # list of {"toolSpec": {...}}
    specs = tool_info["specs"]

    system_prompt = _build_system_prompt(specs)
    messages = build_history_messages(connection_id)
    emitter = Emitter(apigw, connection_id)

    _emit_debug(emitter, "Starting call_bedrock", {"connection_id": connection_id})
    return slow_path(connection_id, messages, system_prompt, tools, emitter)
