import boto3
import json

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("messages")
preferenceTable = dynamodb.Table("session-preferences")
memoryTable = dynamodb.Table("session-memory")


def get_session_messages(connection_id):
    """Return a list of messages for a given WebSocket connection."""
    response = table.get_item(Key={"connectionId": connection_id})
    item = response.get("Item")
    return item.get("messages", []) if item else []


def save_user_message(usermessage, connection_id):
    """Append a user message to the session's message list."""
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
    """Append a bot (assistant) response to the session's message list."""
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
    """Create a new preferences entry if it doesn't already exist."""
    preferenceTable.put_item(
        Item={
            "preferenceKey": sessionid,
            "vehicle_type": {},
            "drive_train": {},
            "num_of_seating": {},
            "overall_stars": {}
        }
    )


def save_user_preference(sessionid, preference):
    """Store or overwrite user preferences."""
    # You can store as raw dict (recommended) or JSON string if you prefer
    preferenceTable.update_item(
        Key={"preferenceKey": sessionid},
        UpdateExpression="SET vehicle_type=:new_preferences, drive_train=:new_drive_train, num_of_seating=:new_num_of_seating, overall_stars=:new_overall_stars",
        ExpressionAttributeValues={
            ":new_preferences": preference,
        },
        ReturnValues="UPDATED_NEW",
    )


def get_user_preferences(sessionid):
    """Retrieve user preferences for a given session."""
    response = preferenceTable.get_item(Key={"preferenceKey": sessionid})
    item = response.get("Item")
    return item.get("preferences", {}) if item else {}


def get_working_state(connection_id):
    """Retrieve the agent's working memory snapshot for this session."""
    try:
        response = table.get_item(Key={"connectionId": connection_id})
        item = response.get("Item")
        return item.get("working_state", {}) if item else {}
    except Exception as e:
        print(f"Error loading working state: {e}")
        return {}

def save_working_state(connection_id, state):
    """Persist the agent's current working memory (e.g. preferences, cars, ratings)."""
    try:
        table.update_item(
            Key={"connectionId": connection_id},
            UpdateExpression="SET working_state = :s",
            ExpressionAttributeValues={":s": state},
        )
    except Exception as e:
        print(f"Error saving working state: {e}")
