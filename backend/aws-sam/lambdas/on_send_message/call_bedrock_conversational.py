import re
from bedrock_caller import call_bedrock
from typing import List, Literal
from pydantic import BaseModel, ValidationError

TARGET_FLAGS = ["number_of_seats"]
TRIGGER_LINE = "Hold on while we gather those recommendations for you..."

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


# === Keyword detection ===
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
    """
    Generate a conversational response for the given connection by calling Bedrock.
    Override the model output if recommendation intent is detected.
    """
    from dynamo_db_helpers import get_session_messages

    raw_messages = get_session_messages(connection_id) or []
    validated_messages: List[ChatMessage] = []
    for m in raw_messages:
        try:
            if m.get("role") in ("user", "assistant"):
                validated_messages.append(ChatMessage(**m))
        except ValidationError:
            continue

    flags_str = ", ".join(f'"{f}"' for f in TARGET_FLAGS)

    system_prompt = (
        "You are an intelligent assistant embedded in a car suggestion tool. "
        "You must always respond concisely and politely, and keep the conversation focused "
        f"on the user's car preferences such as {flags_str}. "
        "When you detect that the user is asking for specific car recommendations or expressing intent "
        "to be recommended a vehicle, you MUST end your message with the exact phrase:\n\n"
        f"{TRIGGER_LINE}\n\n"
        "Make sure that phrase is the final line of your reply. "
        "Do not add any text, punctuation, or commentary after it. "
        "If the user is *not* asking for car recommendations, simply continue the conversation naturally."
    )

    print(f"Calling Bedrock for connection {connection_id} with system prompt:\n{system_prompt}\n")

    # === Force override if user asked for recommendations ===
    if _wants_recommendations(validated_messages):
        print("Detected recommendation intent — overriding model output.")
        return TRIGGER_LINE

    # Otherwise, call Bedrock as usual
    reply = call_bedrock(connection_id, system_prompt)

    # Just in case model partially follows the rule, enforce ending
    if _wants_recommendations(validated_messages):
        return _enforce_trigger(reply)

    return reply or "(no reply from model)"
