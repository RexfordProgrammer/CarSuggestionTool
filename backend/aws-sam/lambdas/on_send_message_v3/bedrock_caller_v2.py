import os
import json
from typing import List, Dict, Any, Optional

import boto3
from dynamo_db_helpers import (
    build_history_messages,
    get_working_state,
    save_working_state,
)
from tools import allowed_tools, tool_specs, dispatch
from target_flags import get_target_flags
from llm_response_processors import extract_text_chunks, extract_tool_uses, join_clean, json_safe, clean, needs_continue_nudge
from models import WorkingState

from emitter import Emitter

ORCHESTRATOR_MODEL = os.getenv("MASTER_MODEL", "ai21.jamba-1-5-large-v1:0")
bedrock = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))




def _build_system_prompt(specs: List[Dict[str, Any]]) -> str:
    flags_str = ", ".join(f'"{f}"' for f in get_target_flags())
    allowed_lines = [f"- `{s.get('name')}`: {s.get('description')}" for s in specs]
    allowed_block = "\n".join(allowed_lines) or "- (no tools available)"
    base_prompt = (
        "You are an intelligent assistant embedded in a car suggestion tool. "
        "Respond naturally. Use available tools when appropriate to retrieve NHTSA data. "
        "Do not invent tool names. If no tool fits, continue the conversation without tools."
    )
    return (
        f"{base_prompt}\n\n"
        "You are an autonomous car-recommendation assistant that may plan and execute several steps.\n"
        "Call tools only when needed. If you can answer from context, do so.\n"
        "When your final answer is ready, do NOT include the token <|DONE|>.\n"
        "Do not print or describe tool calls (no <tool_calls>, JSON, or arguments) — call tools silently.\n\n"
        "Available tools:\n"
        f"{allowed_block}\n\n"
        "Guidance:\n"
        "- Use `fetch_user_preferences` to ANALYZE the conversation so far (not an external API). "
        f"Extract what the user has mentioned (e.g., {flags_str}, brand, budget, body style).\n"
        "- Use `fetch_cars_of_year` to get available cars for a given year.\n"
        "- Use `fetch_safety_ratings` for NHTSA safety ratings.\n"
        "- Use `fetch_gas_milage` for fuel economy.\n"
        "- After each tool call, re-evaluate what to do next.\n"
        "- Keep replies concise and natural.\n"
        "- Use working memory to avoid redundant actions.\n\n"
        "Verification Rules (mandatory):\n"
        "- If the user asks about safety ratings, NHTSA data, VIN/VehicleId, crash tests, MPG/fuel economy, CO₂/emissions, "
        "you MUST call the corresponding tool(s) and base numeric claims on tool results. Do NOT guess or estimate.\n"
        "- If you lack enough inputs (year/make/model), ask a brief clarifying question instead of answering.\n"
    )

def _status_from_tool_uses(tool_uses: List[Dict[str, Any]]) -> str:
    """Make a friendly one-liner for the UI when tools run."""
    parts: List[str] = []
    for tu in tool_uses:
        name = (tu.get("name") or "").strip()
        inp = tu.get("input") or {}
        if name == "fetch_safety_ratings":
            y = inp.get("year"); mk = inp.get("make"); md = inp.get("model")
            parts.append(f"Looking up NHTSA safety ratings for {y} {mk} {md}…")
        elif name == "fetch_gas_milage":
            y = inp.get("year"); mk = inp.get("make"); md = inp.get("model")
            parts.append(f"Fetching fuel economy for {y} {mk} {md}…")
        elif name == "fetch_cars_of_year":
            y = inp.get("year")
            parts.append(f"Collecting model list for {y}…")
        elif name == "fetch_user_preferences":
            parts.append("Analyzing your preferences so far…")
        else:
            parts.append("Working on that…")
    return " ".join(p for p in parts if p) or "Working on that…"

def _should_fast_path(messages: List[Dict[str, Any]]) -> bool:
    """Allow small-talk fast path only; never for safety/mpg/random-car intents."""
    if not messages:
        return False
    try:
        last_user_text = messages[-1]["content"][0]["text"]
    except Exception:
        return False
    if not isinstance(last_user_text, str):
        return False
    q = last_user_text.lower().strip()

    # Block fast-path for tool-worthy intents
    blocked_terms = [
        "safety", "rating", "ratings", "nhtsa",
        "random car", "random vehicle",
        "mpg", "fuel economy", "gas mileage",
        "vin", "vehicle id",
    ]
    if any(term in q for term in blocked_terms):
        return False

    return len(messages) <= 2 and len(q) < 60

def _extract_content_from_resp(resp):
    out_msg = (resp.get("output") or {}).get("message") or {} # Get output from json, get nested message from json
    content = out_msg.get("content") or [] # get content from output message
    return content

def fast_path(system_prompt, messages, emitter: Emitter):
    try:
        resp = bedrock.converse(
            modelId=ORCHESTRATOR_MODEL,
            system=[{"text": system_prompt}],
            messages=messages,
            inferenceConfig={"temperature": 0.5},
        )
        content = _extract_content_from_resp(resp)
        reply = join_clean(extract_text_chunks(content))
        emitter.emit(reply)
        return reply
    except Exception as e:
        reply = f"Sorry—my model call hit an error: {e}"
        emitter.emit(reply)
        return reply


def slow_path(connection_id, messages, system_prompt, tool_config, emitter, allowed_names):
    state = get_working_state(connection_id)

    state = WorkingState.model_validate(state).model_dump()


    MAX_TURNS = 5
    last_emitted: Optional[str] = None  # ✅ track what we actually sent

    for _ in range(MAX_TURNS):
        if needs_continue_nudge(messages):
            messages.append({"role": "user", "content": [{"text": "(continue)"}]})

        system = [{
            "text": system_prompt
                    + "\n\nCurrent working memory:\n"
                    + json.dumps(state, indent=2)
        }]

        try:
            resp = bedrock.converse(
                modelId=ORCHESTRATOR_MODEL,
                system=system,
                messages=messages,
                toolConfig=tool_config,
                inferenceConfig={"temperature": 0.5},
            )
        except Exception as e:
            err = f"Sorry—my model call hit an error: {e}"
            emitter.emit(err)
            return err
        
        content = _extract_content_from_resp(resp)
        tool_uses = extract_tool_uses(content)
        assistant_texts = extract_text_chunks(content)

        if tool_uses:
            status_line = _status_from_tool_uses(tool_uses)
            emitter.emit(status_line)
            last_emitted = status_line
        else:
            reply = join_clean(assistant_texts)
            emitter.emit(reply)
            save_working_state(connection_id, WorkingState.model_validate(state).model_dump())
            return reply

        # Execute tools 
        messages.append({"role": "assistant", "content": content})
        tool_results_content: List[Dict[str, Any]] = []

        for tu in tool_uses:
            emitter.emit("Calling Tool")
            if not isinstance(tu, dict):
                continue
            name = tu.get("name")
            use_id = tu.get("toolUseId")
            tool_input = tu.get("input") or {}
            status = "success"
            
            try:
                result = dispatch(name, connection_id, tool_input)
                result = json_safe(result)

                if isinstance(result, dict):
                    result_content = [{"json": result}]
                elif isinstance(result, str):
                    result_content = [{"text": result}]
                elif isinstance(result, list):
                    result_content = result if result else [{"text": "(no content)"}]
                else:
                    result_content = [{"text": str(result)}]

                # Update working memory
                if name == "fetch_user_preferences" and isinstance(result, dict):
                    try:
                        state.setdefault("preferences", {}).update(result or {})
                    except Exception:
                        pass
                elif name == "fetch_cars_of_year" and isinstance(result, dict):
                    cars = result.get("cars") or result.get("models") or []
                    if isinstance(cars, list):
                        state.setdefault("cars", []).extend(cars)
                elif name == "fetch_safety_ratings":
                    state.setdefault("ratings", []).append(result)
                elif name == "fetch_gas_milage":
                    state.setdefault("gas_data", []).append(result)

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

        save_working_state(connection_id, WorkingState.model_validate(state).model_dump())
        messages.append({"role": "user", "content": tool_results_content})

    return last_emitted or "(no output)"


#################### Main #####################
def call_bedrock(connection_id: str, apigw) -> str:
    tool_info = allowed_tools()
    tool_config = tool_info["tool_config"]
    allowed_names = tool_info["allowed_names"]
    specs = tool_info["specs"]

    system_prompt = _build_system_prompt(specs)
    messages = build_history_messages(connection_id)
    emitter = Emitter(apigw, connection_id)
    
    # # ---- Fast path (strictly small-talk)
    # if _should_fast_path(messages):
        
    #     return fast_path(system_prompt, messages, emitter)
    # else:    
    return slow_path(connection_id, messages, system_prompt, tool_config, emitter, allowed_names)
    