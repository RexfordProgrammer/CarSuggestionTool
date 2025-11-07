import boto3
import json

from dynamo_db_helpers import save_user_message, save_bot_response
from call_bedrock_conversational import get_conversational_response

def push_message_to_caller(connection_id, apigw, message):
    payload = {"type": "bedrock_reply", "reply": message}
    try:
        apigw.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(payload).encode("utf-8")
        )
        print("Sent successfully")
    except Exception as e:
        print("Error posting to connection:", str(e))


def lambda_handler(event, context):
    print("Full event:", json.dumps(event))
    # Session identifiers
    connection_id = event["requestContext"]["connectionId"]
    domain = event["requestContext"]["domainName"]
    stage = event["requestContext"]["stage"]

    # Parse inbound frame
    try:
        body = json.loads(event.get("body") or "{}")
    except Exception as e:
        print("Error parsing body:", e)
        body = {}

    user_message = body.get("text", "(no text)")
    save_user_message(user_message, connection_id)

    # Orchestrate via Bedrock (now with native tool calls)
    conversational_response = get_conversational_response(connection_id)
    save_bot_response(conversational_response, connection_id)

    # Push to caller
    apigw = boto3.client("apigatewaymanagementapi", endpoint_url=f"https://{domain}/{stage}")
    push_message_to_caller(connection_id, apigw, conversational_response)

    return {"statusCode": 200}
