"""Main running portion"""
import os
import json
import boto3

from db_tools_v2 import save_user_message
from bedrock_caller_v2 import call_orchestrator


def lambda_handler(event, context): #pylint: disable=unused-argument
    """Main Entry Point from AWS"""
    connection_id = event["requestContext"]["connectionId"]
    domain = event["requestContext"]["domainName"]
    stage = event["requestContext"]["stage"]

    try:
        body = json.loads(event.get("body") or "{}")
    except Exception: #pylint: disable=broad-exception-caught
        body = {}

    user_message = (body.get("text") or "").strip()
    if user_message:
        save_user_message(connection_id, user_message)
    else:
        save_user_message( connection_id, "(connected)")

    apigw = boto3.client(
        "apigatewaymanagementapi",
        endpoint_url=f"https://{domain}/{stage}",
        region_name=os.getenv("AWS_REGION", "us-east-1"),
    )
    call_orchestrator(connection_id, apigw)
    return {"statusCode": 200}
