import os
import json
import time
import jwt  # pip install pyjwt
import boto3

# Cache the secret so Secrets Manager isn’t called every time
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

def make_response(status_code, body_dict=None):
    """Always return JSON + CORS headers"""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",           # dev: allow all origins
            "Access-Control-Allow-Headers": "*",          # dev: allow all headers
            "Access-Control-Allow-Methods": "OPTIONS,POST"
        },
        "body": json.dumps(body_dict or {})
    }

def get_method(event):
    """Detect HTTP method for REST API v1 or HTTP API v2"""
    if "httpMethod" in event:  # REST API v1
        return event["httpMethod"]
    if "requestContext" in event and "http" in event["requestContext"]:  # HTTP API v2
        return event["requestContext"]["http"].get("method")
    return None

def lambda_handler(event, context):
    try:
        # Debugging – log event in CloudWatch
        print("Incoming event:", json.dumps(event))

        method = get_method(event)

        # Handle preflight CORS
        if method == "OPTIONS":
            return make_response(200)

        # Parse body safely
        raw_body = event.get("body") or "{}"
        if isinstance(raw_body, str):
            body = json.loads(raw_body or "{}")
        elif isinstance(raw_body, dict):
            body = raw_body
        else:
            body = {}

        username = body.get("username")
        password = body.get("password")

        if username != "testuser" or password != "testpass":
            return make_response(401, {"error": "Invalid credentials"})

        # Build JWT payload
        now = int(time.time())
        payload = {
            "sub": username,
            "iat": now,
            "exp": now + 900,
            "roles": ["user"]
        }

        secret = get_jwt_secret()
        token = jwt.encode(payload, secret, algorithm="HS256")

        return make_response(200, {"token": token})

    except Exception as e:
        print("Error:", str(e))
        return make_response(500, {"error": str(e)})
