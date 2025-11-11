from typing import Any, Dict, List
import boto3
import json
from models import ChatMessage, MessageRecord, PreferenceRecord, MemoryRecord

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("messages")
preferenceTable = dynamodb.Table("session-preferences")
memoryTable = dynamodb.Table("session-memory")


def get_session_messages(connection_id):
    """Return a list of messages for a given WebSocket connection."""
    response = table.get_item(Key={"connectionId": connection_id})
    item = response.get("Item") or {"connectionId": connection_id, "messages": []}
    
    #validate item structure
    record = MessageRecord.model_validate(item)
    
    #return list of messages as dicts
    return [m.model_dump for m in record.messages]


def save_user_message(usermessage, connection_id):
    """Append a user message to the session's message list."""
    entry = ChatMessage(role="user", content=usermessage).model_dump
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
    entry = ChatMessage(role="assistant", content=botmessage).model_dump
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

    PreferenceRecord(preferenceKey=sessionid)

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
    if not item:
        return {}
    rec = PreferenceRecord.model_validate(item)

    return {
        "vehicle_type": rec.vehicle_type,
        "drive_train": rec.drive_train,
        "num_of_seating": rec.num_of_seating,
        "overall_stars": rec.overall_stars,
    }


def get_working_state(connection_id):
    """Retrieve the agent's working memory snapshot for this session, with built-in defaults."""
    default_state = {
        "preferences": {},
        "cars": [],
        "ratings": [],
        "gas_data": [],
    }

    try:
        response = table.get_item(Key={"connectionId": connection_id})
        item = response.get("Item")

        # If there's a stored state, merge it with defaults (to ensure all keys exist)
        if item and "working_state" in item:
            stored_state = item["working_state"]
            # Merge: stored values override defaults
            return {**default_state, **stored_state}
    except Exception as e:
        print(f"Error loading working state: {e}")

    return default_state

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

def build_history_messages(connection_id: str) -> List[Dict[str, Any]]:
    raw = get_session_messages(connection_id) or []
    msgs: List[Dict[str, Any]] = []
    for m in raw:
        role = m.get("role")
        content = m.get("content")
        if role in ("user", "assistant") and isinstance(content, str):
            msgs.append({"role": role, "content": [{"text": content}]})
    return msgs