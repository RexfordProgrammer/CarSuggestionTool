import boto3
import json

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

    # Management API client
    apigw = boto3.client(
        "apigatewaymanagementapi",
        endpoint_url=f"https://{domain}/{stage}"
    )

    payload = {
        "type": "echo",
        "reply": f"You said: {message}"
    }

    try:
        print(f"Sending payload: {payload}")
        apigw.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(payload).encode("utf-8")
        )
        print("✅ Sent successfully")
    except Exception as e:
        print("❌ Error posting to connection:", str(e))

    return {"statusCode": 200}
