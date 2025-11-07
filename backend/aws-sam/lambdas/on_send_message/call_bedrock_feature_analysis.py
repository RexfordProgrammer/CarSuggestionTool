import json
from bedrock_caller import call_bedrock

TARGET_FLAGS = ["number_of_seats"]

def get_user_preferences_response(connection_id: str) -> str:
    """
    Analyze the conversation history for mentioned car feature flags.
    Uses the unified Bedrock backend (call_bedrock) which fetches the messages from DynamoDB.
    Ensures the model outputs valid pure JSON — never tool or text formats.
    """
    flags_str = ", ".join(f'"{f}"' for f in TARGET_FLAGS)

    # --- Strict JSON-only system prompt ---
    system_prompt = (
        "SYSTEM ROLE: JSON validator.\n"
        "You must ONLY output a valid JSON object, nothing else.\n\n"
        "TASK:\n"
        f"Given the prior conversation, indicate whether each of the following attributes "
        f"was mentioned: {flags_str}.\n\n"
        "OUTPUT RULES:\n"
        "1. Output **only** a single JSON object — no explanations, no tags, no markdown, no <tool_calls>.\n"
        "2. The output must start with '{' and end with '}'.\n"
        "3. Each key must be one of the listed flags.\n"
        "4. Each value must be true or false.\n"
        "5. Never output XML, YAML, markdown, or any wrapper text.\n\n"
        "Example output:\n{\n  \"number_of_seats\": true\n}\n"
    )

    print(f"Calling Bedrock for preferences with system prompt:\n{system_prompt}\n")
    raw_reply = call_bedrock(connection_id, system_prompt)
    print("Raw reply from Bedrock:", repr(raw_reply))

    # --- Handle empty replies ---
    if not raw_reply:
        print("Warning: Empty reply from Bedrock, returning fallback JSON.")
        return json.dumps({"error": "empty_reply_from_model"})

    # --- Extract JSON portion only ---
    try:
        json_start = raw_reply.index("{")
        json_end = raw_reply.rindex("}") + 1
        json_text = raw_reply[json_start:json_end]
        parsed_flags = json.loads(json_text)
    except Exception as e:
        print("Model did not return valid JSON:", str(e))
        print("Raw model output:", raw_reply)
        parsed_flags = {"error": "invalid_json", "raw_output": raw_reply}

    final = json.dumps(parsed_flags)
    print("Final structured JSON reply:", final)
    return final
