
from decimal import Decimal
import re
from typing import Any, Dict, List, Optional



def join_clean(chunks: List[str]) -> str:
    parts = []
    for t in chunks or []:
        t = clean(t)
        if t:
            parts.append(t)
    return "\n\n".join(parts).strip() or "(no output)"

def last_role(messages: List[Dict[str, Any]]) -> Optional[str]:
    return messages[-1]["role"] if messages else None

def needs_continue_nudge(messages: List[Dict[str, Any]]) -> bool:
    # Only nudge when the last message is an assistant turn.
    return last_role(messages) == "assistant"

def extract_text_chunks(content: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for c in content or []:
        if isinstance(c, dict) and "text" in c and c.get("text"):
            out.append(c["text"])
    return out

def extract_tool_uses(content: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    uses: List[Dict[str, Any]] = []
    for c in content or []:
        if isinstance(c, dict) and "toolUse" in c and isinstance(c["toolUse"], dict):
            uses.append(c["toolUse"])
    return uses
























DONE_LINE_RE   = re.compile(r"(?:^|\n)\s*<\|DONE\|>\s*$", re.IGNORECASE)
DONE_INLINE_RE = re.compile(r"\s*<\|DONE\|>\s*", re.IGNORECASE)
TOOL_MARKUP_RE = re.compile(
    r"(?:</?tool_calls>|\"toolUse\"|\"arguments\"\s*:|<\|\s*tool_(?:call|result)\s*\|>)",
    re.IGNORECASE | re.DOTALL,
)

def strip_done(text: str) -> str:
    if not text:
        return ""
    text = DONE_LINE_RE.sub("", text)
    text = DONE_INLINE_RE.sub("", text)
    return text.strip()

def strip_tool_markup(text: str) -> str:
    if not text:
        return ""
    return TOOL_MARKUP_RE.sub("", text).strip()


def clean(text: str) -> str:
    return strip_done(strip_tool_markup(text or ""))

def json_safe(x):
    if isinstance(x, Decimal):
        return float(x)
    if isinstance(x, dict):
        return {k: json_safe(v) for k, v in x.items()}
    if isinstance(x, list):
        return [json_safe(v) for v in x]
    return x