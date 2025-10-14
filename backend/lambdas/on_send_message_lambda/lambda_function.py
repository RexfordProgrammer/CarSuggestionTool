import boto3
import json

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../../shared"))



bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('messages')

def _get_session_messages(connection_id):
    response = table.get_item(Key={'connectionId': connection_id})
    item = response.get('Item')
    if not item:
        return []
    return item.get('messages', [])


def _get_model_response(connection_id):
    try:
        messages_for_payload = _get_session_messages(connection_id)
        
        system_prompt = {
            "role": "system",
            "content": (
                "You are an intelligent assistant embedded in a car suggestion tool. "
                "Be concise, polite, and guide the user in a conversational way. "
                "If you need clarification, ask brief follow-up questions."
            )
        }

        payload = {
            "messages": [system_prompt] + messages_for_payload,
            "temperature": 0.7
        }
        
        model_id = "ai21.jamba-1-5-mini-v1:0"
        response = bedrock.invoke_model(
            modelId=model_id,
            body=json.dumps(payload)
        )

        result = json.loads(response["body"].read())

        reply = None

        if reply is None:
            try:
                reply = result["choices"][0]["message"]["content"]
            except Exception:
                pass

        return (reply or "(no output)").strip()

    except Exception as e:
        return f"(error from bedrock: {e})"

def _save_message_in_session(usermessage, connection_id):
    entry = {"role": "user", "content": usermessage}
    table.update_item(
        Key={'connectionId': connection_id},
        UpdateExpression="SET messages = list_append(if_not_exists(messages, :empty_list), :new_message)",
        ExpressionAttributeValues={
            ':new_message': [entry],
            ':empty_list': []
        }
    )

def _save_response_in_session(botmessage, connection_id):
    entry = {"role": "assistant", "content": botmessage}
    table.update_item(
        Key={'connectionId': connection_id},
        UpdateExpression="SET messages = list_append(if_not_exists(messages, :empty_list), :new_message)",
        ExpressionAttributeValues={
            ':new_message': [entry],
            ':empty_list': []
        }
    )






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
    _save_message_in_session(user_message, connection_id)

    bedrock_reply = "(no output)"
    bedrock_reply = _get_model_response(connection_id)
    
    _save_response_in_session(bedrock_reply, connection_id)
    
    print ("Chat History: ", _get_session_messages(connection_id))

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
        print("Sent successfully")
    except Exception as e:
        print("Error posting to connection:", str(e))

    return {"statusCode": 200}
