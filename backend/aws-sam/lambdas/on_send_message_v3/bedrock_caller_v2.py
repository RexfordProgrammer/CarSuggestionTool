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

ORCHESTRATOR_MODEL = os.getenv("MASTER_MODEL", "ai21.jamba-1-5-large-v1:0")
bedrock = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))

# Final-answer token contract
DONE_RE = re.compile(r"(?:^|\n)\s*<\|DONE\|>\s*$", re.IGNORECASE)


# ------------------------
# Helpers
# ------------------------
def _strip_done(text: str) -> str:
    return DONE_RE.sub("", text).strip()


def _build_history_messages(connection_id: str) -> List[Dict[str, Any]]:
    """Fetch prior chat and format messages for Bedrock Converse."""
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
    """
    Only nudge when the last message is an assistant turn.
    If the last turn is a user (including toolResult frames), the model already owes a reply.
    """
    return _last_role(messages) == "assistant"


def _extract_text_chunks(content: List[Dict[str, Any]]) -> List[str]:
    """Pull all textual chunks from a Bedrock message content list."""
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
    """Send a piece of assistant text to the client and persist."""
    if not text:
        return
    payload = {"type": "bedrock_reply", "reply": text}
    try:
        apigw.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(payload).encode("utf-8"),
        )
    except Exception:
        # Best-effort emit; don't blow up the turn over socket blips
        pass
    save_bot_response(text, connection_id)


def _build_system_prompt(base_prompt: str, specs: List[Dict[str, Any]]) -> str:
    """Inject tool list and agentic instructions (with final-token contract)."""
    flags_str = ", ".join(f'"{f}"' for f in get_target_flags())
    allowed_lines = [f"- `{s.get('name')}`: {s.get('description')}" for s in specs]
    allowed_block = "\n".join(allowed_lines) or "- (no tools available)"

    return (
        f"{base_prompt}\n\n"
        "You are an autonomous car-recommendation assistant that may plan and execute several steps.\n"
        "Call tools only when needed. If you can answer from context, do so.\n"
        "When your final answer is ready, end with the exact token <|DONE|> on its own line.\n\n"
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


# ------------------------
# Main Orchestrator
# ------------------------
def call_bedrock(connection_id: str, apigw, base_system_prompt: str) -> str:
    """
    Hybrid orchestrator:
      - Fast single-shot path for simple prompts (no tools, low latency)
      - Agentic multi-turn mode for complex flow or when tools are required
      - Streams assistant text to the UI (even during tool rounds)
    Returns the final assistant reply (without the <|DONE|> token).
    """
    tool_info = _allowed_tools()
    tool_config = tool_info["tool_config"]
    allowed_names = tool_info["allowed_names"]
    specs = tool_info["specs"]

    system_prompt = _build_system_prompt(base_system_prompt, specs)
    messages = _build_history_messages(connection_id)

    # ---------------- Fast path ----------------
    try:
        last_user_text = messages[-1]["content"][0]["text"] if messages else ""
    except Exception:
        last_user_text = ""

    if (len(messages) <= 2 and isinstance(last_user_text, str) and len(last_user_text.strip()) < 60):
        try:
            resp = bedrock.converse(
                modelId=ORCHESTRATOR_MODEL,
                system=[{"text": system_prompt}],
                messages=messages,
                inferenceConfig={"temperature": 0.5},
            )
            out_msg = (resp.get("output") or {}).get("message") or {}
            content = out_msg.get("content") or []
            texts = _extract_text_chunks(content)
            reply = "\n\n".join(t.strip() for t in texts if t) or "(no output)"
        except Exception as e:
            reply = f"Sorry—my model call hit an error: {e}"

        if DONE_RE.search(reply):
            reply = _strip_done(reply)

        _emit(reply, connection_id, apigw)
        return reply

    # ---------------- Agentic path ----------------
    state = get_working_state(connection_id) or {
        "preferences": {},
        "cars": [],
        "ratings": [],
        "gas_data": [],
    }

    MAX_TURNS = 5
    last_reply = "(no output)"

    for _ in range(MAX_TURNS):
        # Only nudge if last turn was assistant; otherwise model already owes a reply
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

        # Stream any assistant text immediately (planning/status), but skip the DONE token
        for t in assistant_texts:
            if t and not DONE_RE.search(t):
                t = t.strip()
                if t:
                    _emit(t, connection_id, apigw)
                    last_reply = t

        # If there are NO tool uses, this is a terminal conversational turn
        if not tool_uses:
            reply = "\n\n".join(t.strip() for t in assistant_texts if t) or "(no output)"
            if DONE_RE.search(reply):
                reply = _strip_done(reply)
            _emit(reply, connection_id, apigw)
            save_working_state(connection_id, state)
            return reply

        # ===== Tool execution round =====
        # Append the assistant (toolUse + any text) to the convo
        messages.append({"role": "assistant", "content": content})
        tool_results_content: List[Dict[str, Any]] = []

        for tu in tool_uses:
            if not isinstance(tu, dict):
                continue
            name = tu.get("name")
            use_id = tu.get("toolUseId")
            tool_input = tu.get("input") or {}
            status = "success"

            try:
                if name not in allowed_names:
                    raise ValueError(f"Invalid tool '{name}'")

                result = dispatch(name, connection_id, tool_input)

                # Normalize result to Bedrock toolResult content
                if isinstance(result, dict):
                    result_json = result
                    result_content = [{"json": result_json}]
                elif isinstance(result, str):
                    result_json = {"text": result}
                    result_content = [{"text": result}]
                elif isinstance(result, list):
                    # Expect list of {"json": {...}} or {"text": "..."}
                    result_content = result if result else [{"text": "(no content)"}]
                    # Lightweight best-effort JSON for working memory
                    if result and isinstance(result[0], dict):
                        result_json = result[0].get("json", {}) or {"text": result[0].get("text")}
                    else:
                        result_json = {}
                else:
                    result_json = {"raw": str(result)}
                    result_content = [{"text": str(result)}]

                # Update working memory
                if name == "fetch_user_preferences" and isinstance(result_json, dict):
                    try:
                        state["preferences"].update(result_json or {})
                    except Exception:
                        pass
                elif name == "fetch_cars_of_year" and isinstance(result_json, dict):
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

        # Feed tool results back as a user turn
        save_working_state(connection_id, state)
        messages.append({"role": "user", "content": tool_results_content})

    # Fallback if MAX_TURNS exhausted
    _emit(last_reply, connection_id, apigw)
    save_working_state(connection_id, state)
    return last_reply
