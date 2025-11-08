import re
from bedrock_caller import call_bedrock
from typing import List, Literal
from pydantic import BaseModel, ValidationError
from target_flags import get_target_flags
# TARGET_FLAGS = ["number_of_seats"]
TRIGGER_LINE = "Hold on while we gather those recommendations for you..."

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


def get_conversational_response(connection_id: str) -> str:
    from dynamo_db_helpers import get_session_messages

    raw_messages = get_session_messages(connection_id) or []
    validated_messages: List[ChatMessage] = []
    for m in raw_messages:
        try:
            if m.get("role") in ("user", "assistant"):
                validated_messages.append(ChatMessage(**m))
        except ValidationError:
            continue

    flags_str = ", ".join(f'"{f}"' for f in get_target_flags())

    system_prompt = (
        "You are an intelligent assistant embedded in a car suggestion tool. "
        "Your job is to respond conversationally — never in JSON, XML, YAML, or code format. "
        "Do not produce or reference <tool_calls>, <function_calls>, or any structured data. "
        "Always reply using plain natural language sentences only. "
        "Focus on extracting car preferences and guiding the user toward concrete details "
        f"such as {flags_str}, brand, budget, and body style. "
        "Avoid open-ended questions; when clarification is needed, ask one short, specific question "
        "that helps you collect a missing attribute (e.g., 'Do you prefer SUVs or sedans?'). "
        "Never output lists, schemas, or data structures. "
        "Keep all responses under three sentences. "
        "When the user asks for car recommendations or expresses intent to be shown vehicles, "
        "you MUST end your message with the exact phrase:\n\n"
        f"{TRIGGER_LINE}\n\n"
        "Make sure that phrase is the final line of your reply. "
        "Do not add any text, punctuation, or commentary after it. "
        "If the user is not asking for car recommendations, guide the conversation toward "
        "specific details in a conversational way — not general discussion."
    )



    print(f"Calling Bedrock for connection {connection_id} with system prompt:\n{system_prompt}\n")

    # if _wants_recommendations(validated_messages):
    #     print("Detected recommendation intent — overriding model output.")
    #     return TRIGGER_LINE

    # Otherwise, call Bedrock as usual
    reply = call_bedrock(connection_id, system_prompt)

    # # Just in case model partially follows the rule, enforce ending
    # if _wants_recommendations(validated_messages):
    #     return _enforce_trigger(reply)

    return reply or "(no reply from model)"
