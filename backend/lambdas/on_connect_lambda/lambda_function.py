import json
import jwt
import os
import boto3

# Cache the secret so we don’t call Secrets Manager on every request
_cached_secret = None

def get_jwt_secret():
    global _cached_secret
    if _cached_secret:
        return _cached_secret

    secret_name = os.environ.get("JWT_SECRET_NAME", "JWT_SIGNING_SECRET")
    region_name = os.environ.get("AWS_REGION", "us-east-1")

    client = boto3.client("secretsmanager", region_name=region_name)
    response = client.get_secret_value(SecretId=secret_name)
    _cached_secret = response["SecretString"]
    return _cached_secret

def lambda_handler(event, context):
    print("Connect event:", json.dumps(event))

    token = None
    if "queryStringParameters" in event and event["queryStringParameters"]:
        token = event["queryStringParameters"].get("token")

    if not token:
        return {"statusCode": 401, "body": "Missing token"}

    try:
        secret = get_jwt_secret()
        decoded = jwt.decode(token, secret, algorithms=["HS256"])
        print("JWT valid:", decoded)
        return {"statusCode": 200}  # accept connection
    except jwt.ExpiredSignatureError:
        print("JWT expired")
        return {"statusCode": 401, "body": "Token expired"}
    except Exception as e:
        print("JWT invalid:", str(e))
        return {"statusCode": 401, "body": "Unauthorized"}
