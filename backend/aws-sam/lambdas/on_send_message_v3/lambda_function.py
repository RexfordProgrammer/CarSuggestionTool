import os
import json
import boto3

from db_tools_v2 import save_user_message
from bedrock_caller_v2 import call_orchestrator  # tool-aware orchestrator


def lambda_handler(event, context):
    # Basic request info
    connection_id = event["requestContext"]["connectionId"]
    domain = event["requestContext"]["domainName"]
    stage = event["requestContext"]["stage"]

    # Parse inbound WebSocket frame
    try:
        body = json.loads(event.get("body") or "{}")
    except Exception:
        body = {}

    # Normalize empty/blank messages to avoid LLM "empty content" errors
    user_message = (body.get("text") or "").strip()
    if user_message:
        # Normal path: persist the user message
        save_user_message(connection_id, user_message)
    else:
        # Intentionally record a lightweight placeholder so the model clearly
        # owes a reply on first connect / blank ping.
        save_user_message( connection_id, "(connected)")

    
     # Build API Gateway Management client (needed for streaming emits inside the orchestrator)
    apigw = boto3.client(
        "apigatewaymanagementapi",
        endpoint_url=f"https://{domain}/{stage}",
        region_name=os.getenv("AWS_REGION", "us-east-1"),
    )
    
    call_orchestrator(connection_id, apigw)

    # Always return 200; never drop the socket from handler exceptions
    return {"statusCode": 200}
