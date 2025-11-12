import os
import json
from typing import List, Dict, Any
from decimal import Decimal
import boto3
import botocore

from dynamo_db_helpers import get_session_messages
from db_tools import (
    save_assistant_from_bedrock_resp,
    save_user_bedrock_style,
    append_message_entry,
)
from tools import dispatch, tool_specs
from llm_response_processors import (
    extract_text_chunks,
    extract_tool_uses,
    join_clean,
    needs_continue_nudge,
)
from emitter import Emitter

# ==========================
# CONFIGURATION
# ==========================
ORCHESTRATOR_MODEL = os.getenv("MASTER_MODEL", "ai21.jamba-1-5-large-v1:0")
bedrock = boto3.client(
    "bedrock-runtime",
    region_name=os.getenv("AWS_REGION", "us-east-1"),
    config=botocore.config.Config(connect_timeout=5, read_timeout=15),
)
DEBUG = True
MAX_TURNS = int(os.getenv("MAX_TURNS", "6"))
HISTORY_WINDOW = max(1, int(os.getenv("HISTORY_WINDOW", "10")))


def _preview_tool_result(result, max_lines: int = 40, max_line_chars: int = 200) -> str:
    try:
        if isinstance(result, (dict, list)):
            s = json.dumps(result, ensure_ascii=False, indent=2, default=str)
        else:
            s = str(result)
    except Exception:
        s = str(result)

    lines = s.splitlines()
    clipped = []
    for line in lines[:max_lines]:
        if len(line) > max_line_chars:
            clipped.append(line[:max_line_chars] + "…")
        else:
            clipped.append(line)
    if len(lines) > max_lines:
        clipped.append(f"... [truncated to {max_lines} lines]")
    return "\n".join(clipped)


def _to_native_json(obj):
    """Recursively convert DynamoDB Decimals to int/float and normalize JSON-unsafe types."""
    if isinstance(obj, Decimal):
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    if isinstance(obj, dict):
        return {k: _to_native_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_native_json(v) for v in obj]
    if isinstance(obj, set):
        return [_to_native_json(v) for v in obj]
    if isinstance(obj, (bytes, bytearray)):
        return obj.decode("utf-8", errors="replace")
    return obj


def _normalize_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Guarantee every message has Bedrock-compliant content blocks and native JSON scalars."""
    cleaned = []
    for m in messages:
        role = m.get("role")
        content = m.get("content")

        if isinstance(content, str):
            blocks = [{"text": content}]
        elif isinstance(content, list):
            blocks = content
        else:
            blocks = [{"text": str(content)}]

        blocks = _to_native_json(blocks)
        cleaned.append({"role": role, "content": blocks})
    return cleaned


def _build_system_prompt(specs: List[Dict[str, Any]]) -> str:
    """Construct system prompt with tool listings and optional appended rules."""
    lines = []
    for s in specs:
        ts = s.get("toolSpec", s)
        lines.append(f"- {ts.get('name')}: {ts.get('description')}")
    allowed_block = "\n".join(lines) or "- (no tools available)"

    appendix_text = ""
    appendix_path = os.path.join(os.path.dirname(__file__), "prompt_append.txt")
    if os.path.exists(appendix_path):
        with open(appendix_path, "r", encoding="utf-8") as f:
            appendix_text = f.read().strip()

    base_prompt = (
        "Available tools:\n"
        f"{allowed_block}\n\n"
        "When responding:\n"
        "- Only emit valid `toolUse` blocks when invoking tools.\n"
        "- Never describe tool calls in plain text.\n"
        "- Do NOT include tool JSON in user-visible replies.\n"
        "- Be conversational and concise.\n"
    )
    if appendix_text:
        base_prompt += "\n\nADDITIONAL RULES:\n" + appendix_text + "\n"
    return base_prompt


def get_chat_history(connection_id: str) -> List[Dict[str, Any]]:
    """
    Build windowed, normalized transcript for the model.

    NOTE: This reads from Dynamo (via get_session_messages). All *writes*
    to the transcript go through db_tools now.
    """
    raw_history = get_session_messages(connection_id) or []
    # windowed = _history_window(raw_history)
    safe_history = _normalize_messages(raw_history)

    if needs_continue_nudge(safe_history):
        # Persist a "(continue)" user nudge via db_tools (no tools involved here)
        save_user_bedrock_style(
            connection_id,
            [{"text": "(continue)"}],
        )
        raw_history = get_session_messages(connection_id) or []
        # windowed = _history_window(raw_history)
        safe_history = _normalize_messages(raw_history)

    return safe_history


def main_orchestration(connection_id: str, system_prompt: str, tools: List[Dict[str, Any]], emitter: Emitter):
    '''MAIN ORCHESTRATION'''
    history: List[Dict[str, Any]] = get_chat_history(connection_id)

    for turn in range(MAX_TURNS):
        system_blocks = [{"text": system_prompt}]
        if DEBUG:
            emitter.debug_emit(f"Turn {turn + 1} - ", "Sending System Prompt")

        payload = {
            "modelId": ORCHESTRATOR_MODEL,
            "system": system_blocks,
            "messages": history,
            "toolConfig": {"tools": tools},
            "inferenceConfig": {"temperature": 0.5},
        }
        payload = _to_native_json(payload)

        try:
            resp = bedrock.converse(**payload)
        except Exception as e:
            err = f"Model call failed: {e}"
            emitter.emit(err)
            append_message_entry(
                connection_id,
                {"role": "assistant", "content": [{"text": err}]},
            )
            return err

        # Persist assistant (including any toolUse blocks)
        assistant_entry = save_assistant_from_bedrock_resp(connection_id, resp)
        content = assistant_entry.get("content") or []
        history.append(assistant_entry)

        tool_uses = extract_tool_uses(content)
        assistant_texts = extract_text_chunks(content)

        if DEBUG:
            emitter.debug_emit("Tool Uses:", tool_uses)
            emitter.debug_emit("Assistant Texts Uses:", assistant_texts)

        # ===== Normal conversational reply (no toolUse) OR final turn =====
        if not tool_uses or turn == MAX_TURNS - 1:
            reply = join_clean(assistant_texts)
            if reply:
                emitter.emit(reply)
                # assistant already persisted
                return reply

            # If nothing to say, gently prompt the model on next loop (no tools)
            continue_blocks = [{"text": "(continue)"}]
            history.append({"role": "user", "content": continue_blocks})
            save_user_bedrock_style(connection_id, continue_blocks)
            continue

        # ===== Tool invocation phase =====
        tool_result_blocks: List[Dict[str, Any]] = []

        for tu in tool_uses:
            name = tu.get("name")
            inp = tu.get("input") or {}
            tool_use_id = tu.get("toolUseId")
            emitter.debug_emit("[TOOL CALL]", {"name": name, "input": inp})

            try:
                result = dispatch(name, connection_id, inp)
                emitter.debug_emit(f"Tool result - {name}", result)
                preview_text = _preview_tool_result(result, max_lines=40, max_line_chars=200)
            except Exception as e:
                err_payload = {"error": str(e)}
                emitter.debug_emit("Tool error", err_payload)
                preview_text = _preview_tool_result(err_payload, max_lines=40, max_line_chars=200)

            content_blocks = [{"text": preview_text}]

            tool_result_blocks.append(
                {
                    "toolResult": {
                        "toolUseId": tool_use_id,
                        "content": content_blocks,
                    }
                }
            )

        # Hard guard: never send more toolResult blocks than toolUse blocks
        if len(tool_result_blocks) > len(tool_uses):
            tool_result_blocks = tool_result_blocks[: len(tool_uses)]

        # Append ONE user message with all toolResult blocks for this turn,
        # and DO NOT append a '(continue)' user message after it.
        if tool_result_blocks:
            user_tool_result_entry = {"role": "user", "content": tool_result_blocks}
            history.append(user_tool_result_entry)
            save_user_bedrock_style(connection_id, tool_result_blocks)

        # Next iteration will call converse() again with updated history

    # ========= Fallback if we exit the loop with no reply =========
    fallback = "no more turns"
    emitter.emit(fallback)
    append_message_entry(
        connection_id,
        {"role": "assistant", "content": [{"text": fallback}]},
    )
    return fallback


# ==========================
# ENTRY POINT
# ==========================
def call_bedrock(connection_id: str, apigw):
    """Entry point called from Lambda — orchestrates one round using only transcript memory."""
    tool_info = tool_specs()
    tools = tool_info["tool_config"]["tools"]
    specs = tool_info["specs"]

    system_prompt = _build_system_prompt(specs)
    emitter = Emitter(apigw, connection_id)

    if DEBUG:
        emitter.debug_emit("Starting call_bedrock", {"connection_id": connection_id})

    return main_orchestration(connection_id, system_prompt, tools, emitter)
