# import sys
# import os
# sys.path.append(os.path.join(os.path.dirname(__file__), "../../shared_helpers"))
# Include the above to import this file in your lambda

import json
import boto3
from dynamo_db_helpers import get_session_messages

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

def get_model_response(connection_id):
    try:
        messages_for_payload = get_session_messages(connection_id)
        
        system_prompt = {
            "role": "system",
            "content": (
                "You are an intelligent assistant embedded in a car suggestion tool. "
                "Be concise, polite, and guide the user in a conversational way. "
                "If you need clarification, ask brief follow-up questions."
            )
        }

        payload = {
            "messages": [system_prompt] + messages_for_payload,
            "temperature": 0.7
        }
        
        model_id = "ai21.jamba-1-5-mini-v1:0"
        response = bedrock.invoke_model(
            modelId=model_id,
            body=json.dumps(payload)
        )

        result = json.loads(response["body"].read())

        reply = None

        if reply is None:
            try:
                reply = result["choices"][0]["message"]["content"]
            except Exception:
                pass

        return (reply or "(no output)").strip()

    except Exception as e:
        return f"(error from bedrock: {e})"
