import json
from bedrock_caller import call_bedrock

TARGET_FLAGS = ["number_of_seats"]


def get_user_preferences_response(connection_id: str) -> str:
    """
    Analyze the conversation history for mentioned car feature flags.
    Uses the unified Bedrock backend (call_bedrock) which fetches the messages from DynamoDB.
    """
    flags_str = ", ".join(f'"{f}"' for f in TARGET_FLAGS)

    # --- Strict JSON extraction system prompt ---
    system_prompt = (
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

    print(f"Calling Bedrock for preferences with system prompt:\n{system_prompt}\n")
    raw_reply = call_bedrock(connection_id, system_prompt)
    print("Raw reply from Bedrock:", repr(raw_reply))

    # --- Handle empty or invalid replies ---
    if not raw_reply:
        print("Warning: Empty reply from Bedrock, returning fallback JSON.")
        return json.dumps({"error": "empty_reply_from_model"})

    # --- Attempt to extract valid JSON ---
    try:
        json_text = raw_reply[raw_reply.index("{"): raw_reply.rindex("}") + 1]
        parsed_flags = json.loads(json_text)
    except Exception as e:
        print("Model did not return valid JSON:", str(e))
        print("Raw model output:", raw_reply)
        parsed_flags = {"error": "invalid_json", "raw_output": raw_reply}

    # --- Final structured JSON string ---
    final = json.dumps(parsed_flags)
    print("Final structured JSON reply:", final)
    return final
