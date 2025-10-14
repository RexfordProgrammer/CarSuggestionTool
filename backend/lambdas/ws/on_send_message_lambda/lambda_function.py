import boto3
import json

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('messages')


def _get_model_response(user_message):
    try:
        payload = {
            "messages": [
                {"role": "user", "content": user_message}
            ],
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

def _save_message_in_session (usermessage, connection_id):
    usermessage = "User: "+usermessage
    
    table.update_item(
    Key={'connectionId': connection_id},
    UpdateExpression="SET messages = list_append(if_not_exists(messages, :empty_list), :new_message)",
    ExpressionAttributeValues={
        ':new_message': [usermessage],
        ':empty_list': []
    }
)

def _save_response_in_session (botmessage, connection_id):
    botmessage = "Bot: "+ botmessage
    table.update_item(
    Key={'connectionId': connection_id},
    UpdateExpression="SET messages = list_append(if_not_exists(messages, :empty_list), :new_message)",
    ExpressionAttributeValues={
        ':new_message': [botmessage],
        ':empty_list': []
    }
)

def _get_session_messages(connection_id):
    response = table.get_item(Key={'connectionId': connection_id})
    item = response.get('Item')
    if not item:
        return []
    return item.get('messages', [])





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
    _save_message_in_session(user_message, event['requestContext']['connectionId'])

    bedrock_reply = "(no output)"
    bedrock_reply = _get_model_response(user_message)

    _save_response_in_session(bedrock_reply, event['requestContext']['connectionId'])
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
