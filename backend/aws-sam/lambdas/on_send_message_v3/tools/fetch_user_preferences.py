# tools/fetch_user_preferences.py
import os, json, boto3
from typing import Dict, List
from dynamo_db_helpers import get_session_messages, save_user_preference
from target_flags import get_target_flags

SPEC = {
    "toolSpec": {
        "name": "fetch_user_preferences",
        "description": "Extract which car features (like number_of_seats) the user has mentioned in the conversation.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "flags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of flags to analyze; defaults to standard TARGET_FLAGS."
                    }
                },
                "additionalProperties": False
            }
        }
    }
}

_bedrock = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
_ANALYZER_MODEL = os.getenv("FEATURE_ANALYZER_MODEL", "ai21.jamba-1-5-large-v1:0")


def _llm_detect_flags(history: List[Dict], flags: List[str]) -> Dict[str, bool]:
    convo = []
    for m in history or []:
        if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str):
            convo.append(f"{m['role'].upper()}: {m['content']}")
    transcript = "\n".join(convo)

    system = [{
        "text": (
            "You are a JSON-only classifier. "
            "Given a conversation transcript, output a JSON object whose keys are exactly the requested flags, "
            "indicating if each feature was mentioned or implied. "
            "Respond only with valid JSON — no extra text."
        )
    }]

    user_prompt = (
        f"FLAGS: {json.dumps(flags)}\n\n"
        f"TRANSCRIPT:\n{transcript}\n\n"
        "Return ONLY JSON like: {\"flagA\": true, \"flagB\": false}"
    )

    resp = _bedrock.converse(
        modelId=_ANALYZER_MODEL,
        system=system,
        messages=[{"role": "user", "content": [{"text": user_prompt}]}],
        responseFormat={"type": "json"},
        toolChoice={"type": "none"},
        inferenceConfig={"temperature": 0}
    )

    out = (resp.get("output") or {}).get("message") or {}
    parts = out.get("content") or []
    for p in parts:
        if "json" in p:
            return p["json"]
        if "text" in p:
            try:
                return json.loads(p["text"])
            except Exception:
                pass
    return {k: False for k in flags}


def handle(connection_id: str, tool_input: Dict) -> List[Dict]:
    flags = None
    if isinstance(tool_input, dict):
        flags = tool_input.get("flags")
    if not flags:
        flags = get_target_flags()

    history = get_session_messages(connection_id) or []
    result = _llm_detect_flags(history, flags)
    save_user_preference(connection_id, result)
    return [{"json": result}]
