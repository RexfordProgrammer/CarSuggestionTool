import boto3


dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('messages')

def get_session_messages(connection_id):
    response = table.get_item(Key={'connectionId': connection_id})
    item = response.get('Item')
    if not item:
        return []
    return item.get('messages', [])

def save_message_in_session(usermessage, connection_id):
    entry = {"role": "user", "content": usermessage}
    table.update_item(
        Key={'connectionId': connection_id},
        UpdateExpression="SET messages = list_append(if_not_exists(messages, :empty_list), :new_message)",
        ExpressionAttributeValues={
            ':new_message': [entry],
            ':empty_list': []
        }
    )


def save_response_in_session(botmessage, connection_id):
    entry = {"role": "assistant", "content": botmessage}
    table.update_item(
        Key={'connectionId': connection_id},
        UpdateExpression="SET messages = list_append(if_not_exists(messages, :empty_list), :new_message)",
        ExpressionAttributeValues={
            ':new_message': [entry],
            ':empty_list': []
        }
    )
