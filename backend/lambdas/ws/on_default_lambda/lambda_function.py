import boto3
import json

def lambda_handler(event, context):
    # Test for cli upload

    print("Event:", json.dumps(event))

    connection_id = event["requestContext"]["connectionId"]
    domain = event["requestContext"]["domainName"]
    stage = event["requestContext"]["stage"]

    # Safe parse
    try:
        body = json.loads(event.get("body") or "{}")
    except Exception:
        body = {}

    message = body.get("text", "(no text)")

    # Construct API Gateway Management client
    apigw = boto3.client(
        "apigatewaymanagementapi",
        endpoint_url=f"https://{domain}/{stage}"
    )

    try:
        apigw.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps({"reply": f"You said: {message}"}).encode("utf-8")
        )
    except Exception as e:
        print("Error posting to connection:", e)

    return {"statusCode": 200}
