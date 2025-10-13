import boto3
import json
import os
import requests

def get_bedrock_api_key():
    secrets = boto3.client("secretsmanager", region_name="us-east-1")
    secret_value = secrets.get_secret_value(SecretId="bedrockkey")
    # secret should be stored as {"BEDROCK_API_KEY": "actual-key"}
    return json.loads(secret_value["SecretString"])["BEDROCK_API_KEY"]

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

    user_message = body.get("text", "(no text)")

    # --- Call Bedrock with API Key ---
    try:
        api_key = get_bedrock_api_key()

        url = "https://bedrock-runtime.us-east-1.amazonaws.com/model/meta.llama3-3-70b-instruct-v1:0/invoke"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "inputText": user_message,
            "parameters": {"max_gen_len": 256}
        }

        r = requests.post(url, headers=headers, json=payload)
        r.raise_for_status()
        resp = r.json()

        bedrock_reply = resp.get("outputText", "(no output)")
    except Exception as e:
        print("❌ Bedrock call failed:", str(e))
        bedrock_reply = f"(error from bedrock: {e})"

    # --- Send response via WebSocket ---
    apigw = boto3.client(
        "apigatewaymanagementapi",
        endpoint_url=f"https://{domain}/{stage}"
    )

    payload = {"type": "bedrock_reply", "reply": bedrock_reply}

    try:
        apigw.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(payload).encode("utf-8")
        )
        print("✅ Sent successfully")
    except Exception as e:
        print("❌ Error posting to connection:", str(e))

    return {"statusCode": 200}
