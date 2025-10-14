# import sys
# import os
# sys.path.append(os.path.join(os.path.dirname(__file__), "../../shared_helpers"))

import boto3
import json
from dynamo_db_helpers import get_session_messages, save_message_in_session
from call_bedrock import get_model_response


def lambda_handler(event, context):
    print("Full event:", json.dumps(event))

    connection_id = event["requestContext"]["connectionId"]
    domain = event["requestContext"]["domainName"]
    stage = event["requestContext"]["stage"]

    try:
        body = json.loads(event.get("body") or "{}")
    except Exception as e:
        print("Error parsing body:", e)
        body = {}

    user_message = body.get("text", "(no text)")
    save_message_in_session(user_message, connection_id)

    bedrock_reply = "(no output)"
    bedrock_reply = get_model_response(connection_id)
    
    save_message_in_session(bedrock_reply, connection_id)
    
    print ("Chat History: ", get_session_messages(connection_id))

    apigw = boto3.client(
        "apigatewaymanagementapi",
        endpoint_url=f"https://{domain}/{stage}"
    )

    payload = {"type": "bedrock_reply", "reply": bedrock_reply}

    try:
        apigw.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(payload).encode("utf-8")
        )
        print("Sent successfully")
    except Exception as e:
        print("Error posting to connection:", str(e))

    return {"statusCode": 200}
