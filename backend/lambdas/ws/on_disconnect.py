import json

def lambda_handler(event, context):
    connection_id = event["requestContext"]["connectionId"]
    print(f"Disconnected {connection_id}")
    return {"statusCode": 200, "body": json.dumps({"disconnected": connection_id})}
