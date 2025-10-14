import boto3
import json

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

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

    # --- Call Bedrock: AI21 Jamba 1.5 Mini (chat schema) ---
    model_id = "ai21.jamba-1-5-mini-v1:0"
    bedrock_reply = "(no output)"
    try:
        # IMPORTANT: content must be a STRING for this model
        payload = {
            "messages": [
                {"role": "user", "content": user_message}
            ],
            # keep top-level params minimal; this model rejects some extras
            "temperature": 0.7
            # You can add "topP": 0.9 later if needed
        }

        response = bedrock.invoke_model(
            modelId=model_id,
            body=json.dumps(payload)
        )

        result = json.loads(response["body"].read())
        # Debug once to see exact shape (comment out after verifying)
        print("Raw Bedrock result:", json.dumps(result)[:2000])

        # --- Robust extraction across known AI21/Jamba shapes ---
        reply = None

        # Newer Jamba chat-style (common on Bedrock):
        try:
            reply = result["output"]["message"]["content"][0]["text"]
        except Exception:
            pass

        # Alternate AI21 completion-style:
        if reply is None:
            try:
                reply = result["completions"][0]["data"]["text"]
            except Exception:
                pass

        # OpenAI-like fallback:
        if reply is None:
            try:
                reply = result["choices"][0]["message"]["content"]
            except Exception:
                pass

        # Simple fields fallback:
        if reply is None:
            reply = result.get("outputText") or result.get("result")

        bedrock_reply = (reply or "(no output)").strip()

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
