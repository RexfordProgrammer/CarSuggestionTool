import os
import json
import re
from typing import List, Dict, Any, Optional

import boto3
from dynamo_db_helpers import (
    get_session_messages,
    save_bot_response,
    get_working_state,
    save_working_state,
)
from tools import tool_specs, dispatch
from target_flags import get_target_flags


from decimal import Decimal

def _json_safe(x):
    if isinstance(x, Decimal):
        return float(x)
    if isinstance(x, dict):
        return {k: _json_safe(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_json_safe(v) for v in x]
    return x


ORCHESTRATOR_MODEL = os.getenv("MASTER_MODEL", "ai21.jamba-1-5-large-v1:0")
bedrock = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))

# === Cleanup helpers ===

# Full-line and inline DONE token stripping
DONE_LINE_RE   = re.compile(r"(?:^|\n)\s*<\|DONE\|>\s*$", re.IGNORECASE)
DONE_INLINE_RE = re.compile(r"\s*<\|DONE\|>\s*", re.IGNORECASE)

# Heuristic to spot/strip any tool markup that sneaks into assistant text
TOOL_MARKUP_RE = re.compile(
    r"(?:</?tool_calls>|\"toolUse\"|\"arguments\"\s*:|<\|\s*tool_(?:call|result)\s*\|>)",
    re.IGNORECASE | re.DOTALL,
)

def _strip_done(text: str) -> str:
    if not text:
        return ""
    text = DONE_LINE_RE.sub("", text)
    text = DONE_INLINE_RE.sub("", text)
    return text.strip()

def _strip_tool_markup(text: str) -> str:
    if not text:
        return ""
    return TOOL_MARKUP_RE.sub("", text).strip()

def _clean(text: str) -> str:
    return _strip_done(_strip_tool_markup(text or ""))

# === Message utilities ===

def _build_history_messages(connection_id: str) -> List[Dict[str, Any]]:
    raw = get_session_messages(connection_id) or []
    msgs: List[Dict[str, Any]] = []
    for m in raw:
        role = m.get("role")
        content = m.get("content")
        if role in ("user", "assistant") and isinstance(content, str):
            msgs.append({"role": role, "content": [{"text": content}]})
    return msgs

def _last_role(messages: List[Dict[str, Any]]) -> Optional[str]:
    return messages[-1]["role"] if messages else None

def _needs_continue_nudge(messages: List[Dict[str, Any]]) -> bool:
    # Only nudge when the last message is an assistant turn.
    return _last_role(messages) == "assistant"

def _extract_text_chunks(content: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for c in content or []:
        if isinstance(c, dict) and "text" in c and c.get("text"):
            out.append(c["text"])
    return out

def _extract_tool_uses(content: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    uses: List[Dict[str, Any]] = []
    for c in content or []:
        if isinstance(c, dict) and "toolUse" in c and isinstance(c["toolUse"], dict):
            uses.append(c["toolUse"])
    return uses

def _allowed_tools() -> Dict[str, Any]:
    specs = tool_specs() or []
    tool_config = {"tools": [{"toolSpec": s} for s in specs]} if specs else None
    allowed_names = {s.get("name") for s in specs}
    return {"tool_config": tool_config, "allowed_names": allowed_names, "specs": specs}

def _emit(text: str, connection_id: str, apigw) -> None:
    text = (text or "").strip()
    if not text:
        return
    payload = {"type": "bedrock_reply", "reply": text}
    try:
        apigw.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(payload).encode("utf-8"),
        )
    except Exception:
        pass
    save_bot_response(text, connection_id)

def _join_clean(chunks: List[str]) -> str:
    parts = []
    for t in chunks or []:
        t = _clean(t)
        if t:
            parts.append(t)
    return "\n\n".join(parts).strip() or "(no output)"

def _build_system_prompt(base_prompt: str, specs: List[Dict[str, Any]]) -> str:
    flags_str = ", ".join(f'"{f}"' for f in get_target_flags())
    allowed_lines = [f"- `{s.get('name')}`: {s.get('description')}" for s in specs]
    allowed_block = "\n".join(allowed_lines) or "- (no tools available)"

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
        "- Use working memory to avoid redundant actions.\n"
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

# === Main entry ===

def call_bedrock(connection_id: str, apigw, base_system_prompt: str) -> str:
    tool_info = _allowed_tools()
    tool_config = tool_info["tool_config"]
    allowed_names = tool_info["allowed_names"]
    specs = tool_info["specs"]

    system_prompt = _build_system_prompt(base_system_prompt, specs)
    messages = _build_history_messages(connection_id)

    # ---- Fast path (strictly small-talk)
    if _should_fast_path(messages):
        try:
            resp = bedrock.converse(
                modelId=ORCHESTRATOR_MODEL,
                system=[{"text": system_prompt}],
                messages=messages,
                inferenceConfig={"temperature": 0.5},
            )
            out_msg = (resp.get("output") or {}).get("message") or {}
            content = out_msg.get("content") or []
            reply = _join_clean(_extract_text_chunks(content))
        except Exception as e:
            reply = f"Sorry—my model call hit an error: {e}"
        _emit(reply, connection_id, apigw)
        return reply

    # ---- Agentic path
    state = get_working_state(connection_id) or {
        "preferences": {},
        "cars": [],
        "ratings": [],
        "gas_data": [],
    }

    MAX_TURNS = 5
    last_emitted: str = "(no output)"

    # Alias shim so minor name mismatches don't break calls
    ALIASES = {
        "fetch_safety_rating": "fetch_safety_ratings",
    }

    for _ in range(MAX_TURNS):
        if _needs_continue_nudge(messages):
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
            _emit(err, connection_id, apigw)
            return err

        out_msg = (resp.get("output") or {}).get("message") or {}
        content = out_msg.get("content") or []
        tool_uses = _extract_tool_uses(content)
        assistant_texts = _extract_text_chunks(content)

        if tool_uses:
            # During tool turns, emit a single friendly status line (no leaking tool markup)
            _emit(_status_from_tool_uses(tool_uses), connection_id, apigw)
        else:
            # Terminal conversational turn without tools: emit ONCE, cleaned
            reply = _join_clean(assistant_texts)
            _emit(reply, connection_id, apigw)
            save_working_state(connection_id, state)
            return reply

        # ===== Execute tools =====
        messages.append({"role": "assistant", "content": content})
        tool_results_content: List[Dict[str, Any]] = []

        for tu in tool_uses:
            if not isinstance(tu, dict):
                continue
            name = ALIASES.get(tu.get("name"), tu.get("name"))
            use_id = tu.get("toolUseId")
            tool_input = tu.get("input") or {}
            status = "success"

            try:
                if name not in allowed_names:
                    raise ValueError(f"Invalid tool '{name}'")

                result = dispatch(name, connection_id, tool_input)
                result = _json_safe(result)

                if isinstance(result, dict):
                    result_content = [{"json": result}]
                elif isinstance(result, str):
                    result_content = [{"text": result}]
                elif isinstance(result, list):
                    # Accept either [{"json": {...}}] or [{"text": "..."}]
                    result_content = result if result else [{"text": "(no content)"}]
                else:
                    result_content = [{"text": str(result)}]

                # Update working memory
                if name == "fetch_user_preferences" and isinstance(result, dict):
                    try:
                        state["preferences"].update(result or {})
                    except Exception:
                        pass
                elif name == "fetch_cars_of_year" and isinstance(result, dict):
                    cars = result.get("cars") or result.get("models") or []
                    if isinstance(cars, list):
                        state["cars"].extend(cars)
                elif name == "fetch_safety_ratings":
                    state["ratings"].append(result)
                elif name == "fetch_gas_milage":
                    state["gas_data"].append(result)

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

        # Feed tool results back as a user turn
        save_working_state(connection_id, state)
        messages.append({"role": "user", "content": tool_results_content})

    # Safety valve: if we fall through, emit last message once
    _emit(last_emitted, connection_id, apigw)
    save_working_state(connection_id, state)
    return last_emitted
