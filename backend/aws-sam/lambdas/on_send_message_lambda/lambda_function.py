# import sys
# import os
# sys.path.append(os.path.join(os.path.dirname(__file__), "../../shared_helpers"))

import boto3
import json
from dynamo_db_helpers import get_session_messages, save_user_message
from call_bedrock import get_model_response


def lambda_handler(event, context):
    print("Full event:", json.dumps(event))
    # Session Identifier
    connection_id = event["requestContext"]["connectionId"]
    # API Domain name 
    domain = event["requestContext"]["domainName"]
    stage = event["requestContext"]["stage"]

    try:
        body = json.loads(event.get("body") or "{}")
    except Exception as e:
        print("Error parsing body:", e)
        body = {}

    user_message = body.get("text", "(no text)")
    # this passes the user message to the DB for model context
    save_user_message(user_message, connection_id)

    bedrock_reply = "(no output)"
    ## SINCE THE message has already been passed to the backend 
    ## THE DB to be saved, simply requests the next message in the 
    ## Sequence for the
    bedrock_reply = get_model_response(connection_id)
    
    ## This is just setting up the connection which will end up passing the information back to the user 
    apigw = boto3.client("apigatewaymanagementapi", endpoint_url=f"https://{domain}/{stage}")

    ## this is just a package to return to frontend
    payload = {"type": "bedrock_reply", "reply": bedrock_reply}


    ## ATTEMPT TO RETURN PAYLOAD TO CALLER ##
    try:
        apigw.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(payload).encode("utf-8")
        )
        print("Sent successfully")
    except Exception as e:
        print("Error posting to connection:", str(e))

    return {"statusCode": 200}
