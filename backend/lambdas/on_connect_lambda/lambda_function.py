import json
import jwt
import os
import boto3
import logging
import traceback
from dynamo_db_helpers import initialize_session_messages

logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))
_cached_secret = None

def get_jwt_secret():
    """Fetch and cache JWT secret from AWS Secrets Manager."""
    global _cached_secret
    if _cached_secret:
        return _cached_secret

    secret_name = os.environ.get("JWT_SECRET_NAME", "JWT_SIGNING_SECRET")
    region_name = os.environ.get("AWS_REGION", "us-east-1")

    client = boto3.client("secretsmanager", region_name=region_name)
    try:
        response = client.get_secret_value(SecretId=secret_name)
        _cached_secret = response.get("SecretString")
        logger.info("✅ Retrieved JWT secret from Secrets Manager (%s)", secret_name)
    except Exception as e:
        logger.error("❌ Failed to fetch JWT secret: %s", str(e))
        raise
    return _cached_secret

def lambda_handler(event, context):
    """Handles WebSocket $connect route."""
    logger.info("=== $connect EVENT START ===")

    try:
        # Log raw event
        logger.info("Incoming event: %s", json.dumps(event, indent=2))

        # Extract connection ID
        connection_id = event.get("requestContext", {}).get("connectionId")
        logger.info("Connection ID: %s", connection_id)

        # Initialize conversation/session state
        try:
            initialize_session_messages(connection_id)
            logger.info("✅ Initialized DynamoDB session for connection: %s", connection_id)
        except Exception as e:
            logger.warning("⚠️ Failed to initialize session messages: %s", str(e))

        # Parse token from query string
        qs = event.get("queryStringParameters") or {}
        token = qs.get("token")
        logger.info("Token present: %s", bool(token))

        if not token:
            logger.warning("Missing token in query string.")
            return {
                "statusCode": 401,
                "body": json.dumps({"error": "Missing token"})
            }

        # Validate token
        secret = get_jwt_secret()
        try:
            decoded = jwt.decode(token, secret, algorithms=["HS256"])
            logger.info("✅ JWT valid for user: %s", decoded.get("sub"))
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "Connected successfully", "user": decoded.get("sub")})
            }

        except jwt.ExpiredSignatureError:
            logger.warning("❌ JWT expired")
            return {
                "statusCode": 401,
                "body": json.dumps({"error": "Token expired"})
            }

        except jwt.InvalidTokenError as e:
            logger.warning("❌ Invalid JWT: %s", str(e))
            return {
                "statusCode": 401,
                "body": json.dumps({"error": "Invalid token"})
            }

    except Exception as e:
        logger.error("❌ Unhandled exception in $connect Lambda: %s", str(e))
        logger.error(traceback.format_exc())
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e), "traceback": traceback.format_exc()}),
        }

    finally:
        logger.info("=== $connect EVENT END ===")
