# import sys
# import os
# sys.path.append(os.path.join(os.path.dirname(__file__), "../../shared_helpers"))
# Include the above to import this file in your lambda

import json
import boto3
from typing import List, Dict, Any

from dynamo_db_helpers import get_session_messages

# === Bedrock client ===
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

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
    try:
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
        system_prompt = {
            "role": "system",
            "content": (
                "You are an intelligent assistant embedded in a car suggestion tool. "
                "Be concise, polite, and guide the user in a conversational way. "
                "If you need clarification, ask brief follow-up questions."
            ),
        }

        payload = {
            "messages": [system_prompt] + validated_messages,
            "temperature": 0.7,
        }

        model_id = "ai21.jamba-1-5-mini-v1:0"
        response = bedrock.invoke_model(modelId=model_id, body=json.dumps(payload))

        # Parse the model response
        body_str = response["body"].read()
        result = json.loads(body_str)

        # Safely extract the reply content
        reply = "(no output)"
        try:
            reply = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            print("Unexpected Bedrock response structure:", json.dumps(result, indent=2))

        return reply.strip() if isinstance(reply, str) else "(invalid reply format)"

    except Exception as e:
        return f"(error from bedrock: {e})"
