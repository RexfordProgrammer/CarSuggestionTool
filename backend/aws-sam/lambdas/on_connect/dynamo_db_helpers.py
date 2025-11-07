import boto3
import json

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("messages")
preferenceTable = dynamodb.Table("session-preferences")


def get_session_messages(connection_id):
    response = table.get_item(Key={"connectionId": connection_id})
    item = response.get("Item")
    return item.get("messages", []) if item else []


def save_user_message(usermessage, connection_id):
    entry = {"role": "user", "content": usermessage}
    table.update_item(
        Key={"connectionId": connection_id},
        UpdateExpression="SET messages = list_append(if_not_exists(messages, :empty_list), :new_message)",
        ExpressionAttributeValues={
            ":new_message": [entry],
            ":empty_list": [],
        },
    )


def save_bot_response(botmessage, connection_id):
    entry = {"role": "assistant", "content": botmessage}
    table.update_item(
        Key={"connectionId": connection_id},
        UpdateExpression="SET messages = list_append(if_not_exists(messages, :empty_list), :new_message)",
        ExpressionAttributeValues={
            ":new_message": [entry],
            ":empty_list": [],
        },
    )


def initialize_user_preference(sessionid):
    preferenceTable.put_item(
        Item={
            "preferenceKey": sessionid,
            "preferences": {},  # start with empty dict
        }
    )


def save_user_preference(sessionid, preference):
    preferenceTable.update_item(
        Key={"preferenceKey": sessionid},
        UpdateExpression="SET preferences = :new_preferences",
        ExpressionAttributeValues={
            ":new_preferences": preference,
        },
        ReturnValues="UPDATED_NEW",
    )


def get_user_preferences(sessionid):
    response = preferenceTable.get_item(Key={"preferenceKey": sessionid})
    item = response.get("Item")
    return item.get("preferences", {}) if item else {}

def initialize_session_messages(connection_id):
    greeting = {
        "role": "assistant",
        "content": "Bot: Hello! How can I assist you with your car preferences today?"
    }

    table.put_item(
        Item={
            "connectionId": connection_id,
            "messages": [greeting],
        }
    )