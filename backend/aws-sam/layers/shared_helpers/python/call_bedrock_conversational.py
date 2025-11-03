# import sys
# import os
# sys.path.append(os.path.join(os.path.dirname(__file__), "../../shared_helpers"))
# Include the above to import this file in your lambda

from typing import List, Dict, Any
from bedrock_caller import call_bedrock
from dynamo_db_helpers import get_session_messages

TARGET_FLAGS = ["number_of_seats"]

# === Bedrock client ===

def validate_message(msg: Dict[str, Any]) -> Dict[str, str]:
    """Ensure each message has the correct structure."""
    if not isinstance(msg, dict):
        raise ValueError("Message must be a dictionary.")
    role = msg.get("role")
    content = msg.get("content")
    if not isinstance(role, str) or not isinstance(content, str):
        raise ValueError("Message missing required 'role' or 'content' string fields.")
    return {"role": role, "content": content}


def get_model_response(connection_id: str) -> str:
        # Get chat history from DynamoDB
        messages_for_payload = get_session_messages(connection_id)

        # Validate messages — filter out malformed ones
        validated_messages: List[Dict[str, str]] = []
        for m in messages_for_payload:
            try:
                validated_messages.append(validate_message(m))
            except ValueError as ve:
                print(f"Skipping invalid message: {ve}")

        # Add system prompt at the start
        flags_str = ", ".join(f'"{f}"' for f in TARGET_FLAGS)
        system_prompt = {
            "role": "system",
            "content": (
                "You are an intelligent assistant embedded in a car suggestion tool. "
                "Be concise, polite, and guide the user in a conversational way. "
                "If you need clarification, ask brief follow-up questions."
                f"Guide conversation along lines of {flags_str}"
            ),
        }

        payload = {
            "messages": [system_prompt] + validated_messages,
            "temperature": 0.7,
        }

        return call_bedrock(payload)

