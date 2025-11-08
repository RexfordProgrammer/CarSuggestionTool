import os
import json
import boto3

from dynamo_db_helpers import save_user_message
from bedrock_caller_v2 import call_bedrock  # tool-aware orchestrator


def lambda_handler(event, context):
    # Basic request info
    connection_id = event["requestContext"]["connectionId"]
    domain = event["requestContext"]["domainName"]
    stage = event["requestContext"]["stage"]

    # Build API Gateway Management client (needed for streaming emits inside the orchestrator)
    apigw = boto3.client(
        "apigatewaymanagementapi",
        endpoint_url=f"https://{domain}/{stage}",
        region_name=os.getenv("AWS_REGION", "us-east-1"),
    )

    # Parse inbound WebSocket frame
    try:
        body = json.loads(event.get("body") or "{}")
    except Exception:
        body = {}

    # Normalize empty/blank messages to avoid LLM "empty content" errors
    user_message = (body.get("text") or "").strip()
    if user_message:
        # Normal path: persist the user message
        save_user_message(user_message, connection_id)
    else:
        # Intentionally record a lightweight placeholder so the model clearly
        # owes a reply on first connect / blank ping.
        save_user_message("(connected)", connection_id)

    # Base system prompt; the orchestrator will append tool list and guardrails
    system_prompt = (
        "You are an intelligent assistant embedded in a car suggestion tool. "
        "Respond naturally. Use available tools when appropriate to retrieve NHTSA data. "
        "Do not invent tool names. If no tool fits, continue the conversation without tools."
    )

    # Run the tool-aware orchestrator (it will stream intermediate/final messages itself)
    try:
        _ = call_bedrock(connection_id, apigw, system_prompt)
    except Exception as e:
        # Best-effort error to client (direct post; bypass orchestrator)
        payload = {"type": "bedrock_reply", "reply": f"Sorry—something went wrong: {e}"}
        try:
            apigw.post_to_connection(
                ConnectionId=connection_id,
                Data=json.dumps(payload).encode("utf-8"),
            )
        except Exception:
            pass

    # Always return 200; never drop the socket from handler exceptions
    return {"statusCode": 200}
