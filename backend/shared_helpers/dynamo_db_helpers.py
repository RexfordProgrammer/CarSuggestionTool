import boto3


dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('messages')
preferenceTable = dynamodb.Table('session-preferences')

def get_session_messages(connection_id):
    response = table.get_item(Key={'connectionId': connection_id})
    item = response.get('Item')
    if not item:
        return []
    return item.get('messages', [])

def save_user_message(usermessage, connection_id):
    entry = {"role": "user", "content": usermessage}
    table.update_item(
        Key={'connectionId': connection_id},
        UpdateExpression="SET messages = list_append(if_not_exists(messages, :empty_list), :new_message)",
        ExpressionAttributeValues={
            ':new_message': [entry],
            ':empty_list': []
        }
    )

def save_bot_response(botmessage, connection_id):
    entry = {"role": "assistant", "content": botmessage}
    table.update_item(
        Key={'connectionId': connection_id},
        UpdateExpression="SET messages = list_append(if_not_exists(messages, :empty_list), :new_message)",
        ExpressionAttributeValues={
            ':new_message': [entry],
            ':empty_list': []
        }
    )

#assume preferences is a list or dist of some kind, it'll be implemented later
#once we actually know what preferences we want to store
def initalize_user_preference(username):
    preferenceTable.putItem(
        Item = {
                "preferenceKey": username,
                "preference": []
            }
    )

def save_user_preference(username, preference):
    preferenceTable.update_item(
        Key={'preferenceKey': username}, #sort table by username
        UpdateExpression="SET preferences = :new_preferences)",
        ExpressionAttributeValues={':new_preferences': preference}
    )

def get_user_preferences(username):
    response = table.get_item(Key={'preferenceKey': username})
    item = response.get('Item')
    if not item:
        return []
    return item.get('preference')