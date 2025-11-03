from typing import List
from pydantic import BaseModel, ValidationError
from dynamo_db_helpers import get_session_messages
from bedrock_caller import call_bedrock

TARGET_FLAGS = ["number_of_seats"]

class ChatMessage(BaseModel):
    role: str
    content: str


def get_model_response(connection_id: str) -> str:
    """Retrieve messages, validate with Pydantic, and call Bedrock."""

    raw_messages = get_session_messages(connection_id) or []
    print("Raw messages returned:", raw_messages)
    raw_messages = raw_messages or []

    validated_messages: List[ChatMessage] = []
    for m in raw_messages:
        try:
            validated_messages.append(ChatMessage(**m))
        except ValidationError as ve:
            print(f"Skipping invalid message: {ve}")

    # Build system prompt
    flags_str = ", ".join(f'"{f}"' for f in TARGET_FLAGS)
    system_prompt = ChatMessage(
        role="system",
        content=(
            "You are an intelligent assistant embedded in a car suggestion tool. "
            "Be concise, polite, and guide the user in a conversational way. "
            "If you need clarification, ask brief follow-up questions. "
            f"Guide conversation along lines of {flags_str}."
        ),
    )

    payload = {
        "messages": [system_prompt.model_dump()] + [msg.model_dump() for msg in validated_messages],
        "temperature": 0.7,
    }

    print("Payload prepared for Bedrock:", payload)
    return call_bedrock(payload)
