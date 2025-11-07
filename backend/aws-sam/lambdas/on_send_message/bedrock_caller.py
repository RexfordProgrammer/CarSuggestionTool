import boto3
import json
from dynamo_db_helpers import get_session_messages, save_bot_response

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")


def call_bedrock(connection_id: str, system_prompt: str) -> str:
    try:
        raw_messages = get_session_messages(connection_id) or []
        print(f"Fetched {len(raw_messages)} messages for session {connection_id}")

        jamba_messages = [{"role": "system", "content": system_prompt}]
        for msg in raw_messages:
            role = msg.get("role")
            content = msg.get("content")
            if role in ("user", "assistant") and isinstance(content, str):
                jamba_messages.append({"role": role, "content": content})

        body = {
            "messages": jamba_messages,
            "temperature": 0.5,
        }

        print("Prepared Jamba payload:", json.dumps(body, indent=2))

        response = bedrock.invoke_model(
            modelId="ai21.jamba-1-5-large-v1:0",
            body=json.dumps(body),
        )

        body_str = response["body"].read()
        result = json.loads(body_str)

        if "outputText" in result:
            reply = result["outputText"]
        else:
            try:
                reply = result["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError):
                print("Unexpected Bedrock response:", json.dumps(result, indent=2))
                reply = "(no output)"

        if isinstance(reply, str):
            save_bot_response(reply, connection_id)
            return reply.strip()
        else:
            return "(invalid reply format)"

    except Exception as e:
        print("Error in call_bedrock:", str(e))
        return f"(error from bedrock: {e})"
