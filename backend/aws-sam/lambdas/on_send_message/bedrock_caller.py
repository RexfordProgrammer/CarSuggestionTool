import boto3
import json

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

def call_bedrock(payload):
    try:
        model_id = "ai21.jamba-1-5-mini-v1:0"
        system_text = payload.get("system", "")
        messages = payload.get("messages", [])
        temperature = payload.get("temperature", 0.2)
        max_tokens = payload.get("max_tokens", 500)

        # --- Compose message format for Jamba ---
        jamba_messages = []
        if system_text:
            jamba_messages.append({"role": "system", "content": system_text})

        for msg in messages:
            if msg["role"] not in ("user", "assistant"):
                continue
            jamba_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        body = {
            "messages": jamba_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # --- Call Bedrock model ---
        response = bedrock.invoke_model(
            modelId=model_id,
            body=json.dumps(body)
        )

        # --- Parse model response ---
        body_str = response["body"].read()
        result = json.loads(body_str)

        # Jamba responses use `output_text` for simplicity
        if "output_text" in result:
            reply = result["output_text"]
        else:
            try:
                reply = result["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError):
                print("Unexpected Bedrock response structure:", json.dumps(result, indent=2))
                reply = "(no output)"

        return reply.strip() if isinstance(reply, str) else "(invalid reply format)"

    except Exception as e:
        return f"(error from bedrock: {e})"
