import boto3
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
import json

def call_bedrock(payload):
    try:
        model_id = "ai21.jamba-1-5-mini-v1:0"
        response = bedrock.invoke_model(modelId=model_id, body=json.dumps(payload))

        # Parse the model response
        body_str = response["body"].read()
        result = json.loads(body_str)

        # Safely extract the reply content
        reply = "(no output)"
        try:
            reply = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            print("Unexpected Bedrock response structure:", json.dumps(result, indent=2))

        return reply.strip() if isinstance(reply, str) else "(invalid reply format)"
    except Exception as e: 
        return f"(error from bedrock: {e})"