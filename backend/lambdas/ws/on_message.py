import json, boto3, os
apigw = boto3.client("apigatewaymanagementapi", endpoint_url=os.environ.get("WS_ENDPOINT"))

def lambda_handler(event, context):
    connection_id = event["requestContext"]["connectionId"]
    body = json.loads(event.get("body", "{}"))
    msg = body.get("message", "")
    response = {"echo": msg}

    try:
        apigw.post_to_connection(ConnectionId=connection_id, Data=json.dumps(response).encode())
    except Exception as e:
        print(f"Send failed: {e}")

    return {"statusCode": 200, "body": "Processed"}
