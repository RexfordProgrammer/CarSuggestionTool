# import sys
# import os
# sys.path.append(os.path.join(os.path.dirname(__file__), "../../shared_helpers"))
# Include the above to import this file in your lambda

import json
import boto3
from pydantic import BaseModel, ValidationError, Field
from typing import List, Optional, Dict, Any

from dynamo_db_helpers import get_session_messages


# === Define payload models ===
class Message(BaseModel):
    role: str
    content: str


class BedrockPayload(BaseModel):
    messages: List[Message]
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


class BedrockResponseChoice(BaseModel):
    message: Dict[str, Any]


class BedrockResponse(BaseModel):
    choices: List[BedrockResponseChoice]


# === Bedrock client ===
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")


def get_model_response(connection_id: str) -> str:
    try:
        messages_for_payload = get_session_messages(connection_id)

        # Validate messages — ensure they match the expected structure
        validated_messages = [Message(**m) for m in messages_for_payload]

        system_prompt = Message(
            role="system",
            content=(
                "You are an intelligent assistant embedded in a car suggestion tool. "
                "Be concise, polite, and guide the user in a conversational way. "
                "If you need clarification, ask brief follow-up questions."
            )
        )

        payload_obj = BedrockPayload(messages=[system_prompt] + validated_messages)
        payload_json = payload_obj.json()

        model_id = "ai21.jamba-1-5-mini-v1:0"
        response = bedrock.invoke_model(
            modelId=model_id,
            body=payload_json
        )

        result = json.loads(response["body"].read())

        # Validate structure of response (optional, but good for catching errors)
        try:
            parsed_response = BedrockResponse(**result)
            reply = parsed_response.choices[0].message.get("content", "(no output)")
        except ValidationError as e:
            print("Response validation failed:", e)
            reply = result.get("choices", [{}])[0].get("message", {}).get("content", "(no output)")

        return reply.strip()

    except ValidationError as e:
        return f"(validation error: {e})"
    except Exception as e:
        return f"(error from bedrock: {e})"
