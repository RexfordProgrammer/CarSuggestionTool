import boto3
import json
import os

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

    message = body.get("text", "(no text)")

    # Construct the Management API client for *this stage/domain*
    apigw = boto3.client(
        "apigatewaymanagementapi",
        endpoint_url=f"https://{domain}/{stage}"
    )

    try:
        response = apigw.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps({
                "type": "echo",
                "reply": f"You said: {message}"
            }).encode("utf-8")
        )
        print("PostToConnection response:", response)
    except Exception as e:
        print("Error posting to connection:", e)

    return {"statusCode": 200}
