import json
import boto3
from typing import List, Dict, Any

from dynamo_db_helpers import get_session_messages

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

# Define your known flag names here — easy to expand later
TARGET_FLAGS = [
    "number_of_seats",
    "fuel_efficiency",
    "cargo_space",
    "safety_rating"
]


def validate_message(msg: Dict[str, Any]) -> Dict[str, str]:
    if not isinstance(msg, dict):
        raise ValueError("Message must be a dictionary.")
    role = msg.get("role")
    content = msg.get("content")
    if not isinstance(role, str) or not isinstance(content, str):
        raise ValueError("Message missing required 'role' or 'content' string fields.")
    return {"role": role, "content": content}


def get_model_response(connection_id: str) -> str:
    """
    Use the Bedrock LLM to determine which feature flags are checked or unchecked
    based on the conversation.
    """
    try:
        messages_for_payload = get_session_messages(connection_id)

        validated_messages: List[Dict[str, str]] = []
        for m in messages_for_payload:
            try:
                validated_messages.append(validate_message(m))
            except ValueError as ve:
                print(f"Skipping invalid message: {ve}")

        # Construct the dynamic system prompt with the explicit flag set
        flags_str = ", ".join(f'"{f}"' for f in TARGET_FLAGS)
        system_prompt = {
            "role": "system",
            "content": (
                f"You are an assistant analyzing a conversation to determine which "
                f"car feature flags are checked or unchecked.\n\n"
                f"The available flags to analyze are: {flags_str}.\n\n"
                "Return your answer as a JSON object where each key is one of these flags "
                "and each value is true (checked) or false (unchecked).\n"
                "If a flag was not mentioned, mark it false.\n\n"
                "Example output:\n"
                "{\n"
                "  \"number_of_seats\": true,\n"
                "  \"fuel_efficiency\": false,\n"
                "  \"cargo_space\": false,\n"
                "  \"safety_rating\": false\n"
                "}\n\n"
                "Output only JSON — no explanations, text, or commentary."
            ),
        }

        payload = {
            "messages": [system_prompt] + validated_messages,
            "temperature": 0.2,
        }

        model_id = "ai21.jamba-1-5-mini-v1:0"
        response = bedrock.invoke_model(modelId=model_id, body=json.dumps(payload))

        body_str = response["body"].read()
        result = json.loads(body_str)

        reply = None
        try:
            reply = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            print("Unexpected Bedrock response structure:", json.dumps(result, indent=2))
            reply = "(no output)"

        try:
            flags = json.loads(reply)
        except Exception:
            print("Model did not return valid JSON, raw reply:", reply)
            flags = {"error": "invalid_json", "raw_output": reply}

        return json.dumps(flags)

    except Exception as e:
        return json.dumps({"error": f"bedrock_call_failed: {e}"})
