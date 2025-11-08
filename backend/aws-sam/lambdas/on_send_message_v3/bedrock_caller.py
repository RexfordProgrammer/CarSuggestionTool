# bedrock_caller.py
import boto3, json
import os
from dynamo_db_helpers import get_session_messages, save_bot_response
from tools import tool_specs, dispatch

ORCHESTRATOR_MODEL = os.getenv("MASTER_MODEL", "ai21.jamba-1-5-large-v1:0")
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

def _build_converse_messages(connection_id: str, system_prompt: str):
    raw_messages = get_session_messages(connection_id) or []
    system = [{"text": system_prompt}]
    messages = []
    for m in raw_messages:
        role = m.get("role")
        content = m.get("content")
        if role in ("user", "assistant") and isinstance(content, str):
            messages.append({"role": role, "content": [{"text": content}]})
    return system, messages

def call_bedrock(connection_id: str, system_prompt: str) -> str:
    try:
        system, messages = _build_converse_messages(connection_id, system_prompt)

        resp = bedrock.converse(
            modelId=ORCHESTRATOR_MODEL,
            system=system,
            messages=messages,
            toolConfig={"tools": tool_specs()},
            inferenceConfig={"temperature": 0.5},
        )

        out_msg = (resp.get("output") or {}).get("message") or {}
        content = out_msg.get("content") or []
        tool_uses = [c.get("toolUse") for c in content if "toolUse" in c]

        if tool_uses:
            messages_plus = messages + [{"role": "assistant", "content": content}]
            for tu in tool_uses:
                name = tu.get("name")
                use_id = tu.get("toolUseId")
                tool_input = tu.get("input") or {}
                result_content = dispatch(name, connection_id, tool_input)

                messages_plus.append({
                    "role": "tool",
                    "content": [{
                        "toolResult": {
                            "toolUseId": use_id,
                            "content": result_content
                        }
                    }]
                })

            resp2 = bedrock.converse(
                modelId=ORCHESTRATOR_MODEL,
                system=system,
                messages=messages_plus,
                toolConfig={"tools": tool_specs()},
                inferenceConfig={"temperature": 0.5},
            )
            out_msg = (resp2.get("output") or {}).get("message") or {}
            content = out_msg.get("content") or []

        texts = [c.get("text") for c in content if "text" in c]
        reply = (texts[0] if texts else "(no output)").strip()
        save_bot_response(reply, connection_id)
        return reply

    except Exception as e:
        return f"(error from bedrock: {e})"
