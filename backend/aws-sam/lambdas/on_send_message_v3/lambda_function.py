import boto3
import json

from dynamo_db_helpers import save_user_message
from bedrock_caller import call_bedrock  # tool-aware orchestrator

def push_message_to_caller(connection_id, apigw, message: str) -> None:
    payload = {"type": "bedrock_reply", "reply": message}
    apigw.post_to_connection(
        ConnectionId=connection_id,
        Data=json.dumps(payload).encode("utf-8"),
    )

def lambda_handler(event, context):
    # Basic request info
    connection_id = event["requestContext"]["connectionId"]
    domain = event["requestContext"]["domainName"]
    stage = event["requestContext"]["stage"]

    # Parse inbound message (WebSocket frame)
    try:
        body = json.loads(event.get("body") or "{}")
    except Exception:
        body = {}

    # Normalize empty/blank messages to avoid LLM "empty content" errors
    user_message = (body.get("text") or "").strip()
    if user_message:
        save_user_message(user_message, connection_id)
    else:
        # Optionally avoid saving blanks; still run the orchestrator on history
        user_message = "(connected)"

    # System prompt (base); bedrock_caller will append allowed tool list and guardrails
    system_prompt = (
        "You are an intelligent assistant embedded in a car suggestion tool. "
        "Respond naturally. Use available tools when appropriate to retrieve NHTSA data. "
        "Do not invent tool names. If no tool fits, continue the conversation without tools."
    )

    # Run the tool-aware orchestrator
    reply = call_bedrock(connection_id, system_prompt)

    # Push to client
    apigw = boto3.client(
        "apigatewaymanagementapi",
        endpoint_url=f"https://{domain}/{stage}",
    )
    try:
        push_message_to_caller(connection_id, apigw, reply)
    except Exception as e:
        # Log but still return 200 so the socket doesn't get dropped
        print("Error posting to connection:", str(e))

    return {"statusCode": 200}
