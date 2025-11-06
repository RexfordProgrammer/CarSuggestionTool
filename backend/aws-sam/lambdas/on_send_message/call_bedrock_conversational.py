from typing import List, Literal
from pydantic import BaseModel, ValidationError
import re

from dynamo_db_helpers import get_session_messages
from bedrock_caller import call_bedrock

TARGET_FLAGS = ["number_of_seats"]
TRIGGER_LINE = "Hold on while we gather those recommendations for you..."

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str

# Keywords that signal a recommendation request
KEYWORDS_RECO = re.compile(
    r"\b(recommend|reccomend|suggest|what (?:car|vehicle) should I|get|show.+cars?)\b",
    re.IGNORECASE
)

def _wants_recommendations(validated_messages: List[ChatMessage]) -> bool:
    """Detect whether the user's last message asked for car recommendations."""
    for msg in reversed(validated_messages):
        if msg.role == "user":
            return bool(KEYWORDS_RECO.search(msg.content))
    return False

def _enforce_trigger(text: str) -> str:
    """Guarantee the system trigger line appears exactly once at the end."""
    idx = text.lower().rfind(TRIGGER_LINE.lower())
    if idx != -1:
        return text[: idx + len(TRIGGER_LINE)]
    text = text.rstrip()
    if text and not text.endswith((".", "!", "?")):
        text += "."
    return f"{text}\n{TRIGGER_LINE}"

def get_conversational_response(connection_id: str) -> str:
    """Retrieve recent session messages, validate, call Bedrock, and enforce the system trigger."""
    raw_messages = get_session_messages(connection_id) or []
    print("Raw messages returned:", raw_messages)

    validated_messages: List[ChatMessage] = []
    for m in raw_messages:
        try:
            if m.get("role") in ("user", "assistant"):
                validated_messages.append(ChatMessage(**m))
        except ValidationError as ve:
            print(f"Skipping invalid message: {ve}")

    # --- Construct system instructions ---
    flags_str = ", ".join(f'"{f}"' for f in TARGET_FLAGS)
    system_instructions = (
        "You are an intelligent assistant embedded in a car suggestion tool. "
        "Be concise, polite, and guide the user naturally. "
        "Ask short follow-up questions only if clarification is needed. "
        f"Focus the conversation on attributes such as {flags_str}. "
        "When the user asks for car recommendations or expresses intent to get suggestions, "
        f'you MUST end your reply with exactly this line on its own: "{TRIGGER_LINE}" '
        "and do not write anything after that line."
    )

    payload = {
        "system": system_instructions,
        "messages": [m.model_dump() for m in validated_messages],
        "temperature": 0.2,
        "max_tokens": 500
    }

    print("Payload prepared for Bedrock (AI21 Jamba):", payload)
    reply = call_bedrock(payload) or ""

    if _wants_recommendations(validated_messages):
        reply = _enforce_trigger(reply)

    return reply
