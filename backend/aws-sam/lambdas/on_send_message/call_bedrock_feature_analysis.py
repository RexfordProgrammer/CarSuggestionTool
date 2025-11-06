from typing import List, Literal
from pydantic import BaseModel, ValidationError
import json
import re

from dynamo_db_helpers import get_session_messages
from bedrock_caller import call_bedrock

TARGET_FLAGS = ["number_of_seats"]

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


def get_user_preferences_response(connection_id: str) -> str:
    """Retrieve messages, validate, call Bedrock, and interpret structured JSON preferences."""

    # --- Retrieve prior conversation from DynamoDB ---
    raw_messages = get_session_messages(connection_id) or []
    print("Raw messages returned:", raw_messages)

    validated_messages: List[ChatMessage] = []
    for m in raw_messages:
        try:
            if m.get("role") in ("user", "assistant"):
                validated_messages.append(ChatMessage(**m))
        except ValidationError as ve:
            print(f"Skipping invalid message: {ve}")

    # Fallback if no messages found
    if not validated_messages:
        print("No messages found; using default fallback message.")
        validated_messages.append(ChatMessage(role="user", content="Find me a car with 5 seats"))

    # --- System instructions ---
    flags_str = ", ".join(f'"{f}"' for f in TARGET_FLAGS)
    system_instructions = (
        "You are a strict JSON generator analyzing the conversation to determine which "
        "car feature flags were mentioned. The available flags are: "
        f"{flags_str}. Return ONLY valid JSON where each key is one of these flags "
        "and each value is true (mentioned) or false (not mentioned). "
        "If a flag wasn't mentioned, mark it false.\n\n"
        "Example output:\n{\n  \"number_of_seats\": true\n}\n"
        "Rules:\n1. Output must start with '{' and end with '}'.\n"
        "2. Do not include explanations or commentary.\n"
        "3. Never write anything outside the JSON object."
    )

    # --- Payload identical to conversational format ---
    payload = {
        "system": system_instructions,
        "messages": [m.model_dump() for m in validated_messages],
        "temperature": 0.0,
        "max_tokens": 200,
    }

    print("Payload prepared for Bedrock (unified structure):", json.dumps(payload, indent=2))

    # --- Bedrock call ---
    raw_reply = call_bedrock(payload)
    print("Raw reply from Bedrock:", repr(raw_reply))

    if not raw_reply:
        print("Warning: Empty reply from Bedrock, returning fallback JSON.")
        return json.dumps({"error": "empty_reply_from_model"})

    # --- Extract valid JSON if the model adds extra text ---
    try:
        json_text = raw_reply[raw_reply.index("{"): raw_reply.rindex("}") + 1]
        parsed_flags = json.loads(json_text)
    except Exception as e:
        print("Model did not return valid JSON:", str(e))
        print("Raw model output:", raw_reply)
        parsed_flags = {"error": "invalid_json", "raw_output": raw_reply}

    # Always return a string
    final = json.dumps(parsed_flags)
    print("Final structured JSON reply:", final)
    return final
