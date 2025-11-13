
from decimal import Decimal
import re
from typing import Any, Dict, List, Optional


def _strip_full_repeats(text: str) -> str:
    """
    Detects cases like 'X X', 'X X X', etc. (exact repetition of the
    same block 2–5 times) and returns just 'X'.
    """
    candidate = text.strip()
    if not candidate:
        return text

    # Try N copies where N is small (we only care about obvious glitches)
    for n in range(2, 6):
        if len(candidate) % n != 0:
            continue
        unit_len = len(candidate) // n
        unit = candidate[:unit_len]
        if unit * n == candidate:
            return unit.strip()

    return text


def join_clean(chunks: Optional[List[str]]) -> str:
    """
    Join a list of raw model text chunks into a single clean string.

    - Handles None / empty input
    - Runs `clean()` on each chunk
    - Normalizes spaces / newlines
    - Drops empty chunks
    - Drops consecutive duplicate chunks
    - Collapses obvious 'same message repeated N times' patterns
    """
    if not chunks:
        return "(no output)"

    parts: List[str] = []

    for raw in chunks:
        if not raw:
            continue

        # Your existing cleaner
        t = clean(raw)
        if not t:
            continue

        # Normalize whitespace a bit
        t = re.sub(r"[ \t]+", " ", t)      # collapse runs of spaces/tabs
        t = re.sub(r"\n{3,}", "\n\n", t)   # max 2 consecutive newlines
        t = t.strip()

        if not t:
            continue

        # Drop exact consecutive duplicates
        if parts and t == parts[-1]:
            continue

        parts.append(t)

    if not parts:
        return "(no output)"

    joined = "\n\n".join(parts).strip()

    # Handle pathological “full message duplicated” cases
    joined = _strip_full_repeats(joined)

    return joined or "(no output)"

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