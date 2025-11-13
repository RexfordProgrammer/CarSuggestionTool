from typing import Any, Dict, List, Optional
import json
from decimal import Decimal


# ==========================
# BLOCK NORMALIZATION
# ==========================
def normalize_bedrock_blocks(content: Any) -> List[Dict[str, Any]]:
    """
    Convert arbitrary content (string or list or dict) into valid Bedrock text-blocks.
    Does NOT strip toolUse or toolResult: those should be passed in already formed.
    """
    if isinstance(content, list):
        return content
    if isinstance(content, dict):
        return [content]
    return [{"text": str(content)}]


# ==========================
# SPLITTING ASSISTANT
# ==========================
def split_mixed_assistant(entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    If an assistant message contains BOTH text and toolUse blocks, split into:
      1. assistant with only text
      2. assistant with only toolUse
    """
    if entry.get("role") != "assistant":
        return [entry]

    content = entry.get("content") or []
    text_blocks = [b for b in content if isinstance(b, dict) and "text" in b]
    tooluse_blocks = [b for b in content if isinstance(b, dict) and "toolUse" in b]

    if text_blocks and tooluse_blocks:
        return [
            {"role": "assistant", "content": text_blocks},
            {"role": "assistant", "content": tooluse_blocks},
        ]

    return [entry]


# ==========================
# EXTRACTION UTILITIES
# ==========================
def extract_text_blocks(content: List[Dict[str, Any]]) -> List[str]:
    out = []
    for c in content or []:
        if isinstance(c, dict) and "text" in c:
            out.append(str(c["text"]))
    return out


def extract_tool_uses(content: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    uses = []
    for c in content or []:
        if isinstance(c, dict) and isinstance(c.get("toolUse"), dict):
            uses.append(c["toolUse"])
    return uses


def get_content_blocks(resp_or_msg: Dict[str, Any]) -> List[Dict[str, Any]]:
    if "output" in resp_or_msg:
        resp_or_msg = resp_or_msg.get("output", {}).get("message", {}) or {}
    content = resp_or_msg.get("content") or []
    return content if isinstance(content, list) else [content]


def get_first_tool_use(resp: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    content = get_content_blocks(resp)
    uses = extract_tool_uses(content)
    return uses[0] if uses else None


def get_all_text_from_resp(resp: Dict[str, Any], sep=" ") -> str:
    blocks = get_content_blocks(resp)
    texts = extract_text_blocks(blocks)
    return sep.join(texts).strip()


# ==========================
# TEXT PREVIEW / CLIPPING
# ==========================
def preview_tool_result(result, max_lines=40, max_line_chars=200) -> str:
    try:
        s = json.dumps(result, ensure_ascii=False, indent=2)
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


# ==========================
# JSON SAFE HELPERS
# ==========================
def json_safe(x):
    if isinstance(x, Decimal):
        return float(x)
    if isinstance(x, dict):
        return {k: json_safe(v) for k, v in x.items()}
    if isinstance(x, list):
        return [json_safe(v) for v in x]
    return x


def to_native_json(obj):
    if isinstance(obj, Decimal):
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    if isinstance(obj, dict):
        return {k: to_native_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_native_json(v) for v in obj]
    if isinstance(obj, (bytes, bytearray)):
        return obj.decode("utf-8", errors="replace")
    return obj
