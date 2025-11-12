from typing import Any, Dict, List
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

def _truncate_state(state: Dict[str, Any], max_items: int = 10, max_chars: int = 2000) -> Dict[str, Any]:
    """
    Safely trim oversized working state before persisting to DynamoDB.
    Prevents large payloads (e.g., full vehicle lists) from breaking LLM calls.
    """
    state = dict(state or {})

    # --- Trim long lists like cars, ratings, gas_data ---
    for key in ("cars", "ratings", "gas_data"):
        val = state.get(key)
        if isinstance(val, list) and len(val) > max_items:
            state[key] = val[:max_items]
            state[f"{key}_summary"] = f"{len(val)} total items (showing first {max_items})"
            print(f"⚠️ Truncated {key}: kept {max_items} of {len(val)} items")

    # --- Trim large text blobs inside preferences ---
    prefs = state.get("preferences", {})
    if isinstance(prefs, dict):
        total_len = sum(len(str(v)) for v in prefs.values())
        if total_len > max_chars:
            short_prefs = {k: (str(v)[:100] + "…") for k, v in prefs.items()}
            state["preferences"] = short_prefs
            state["preferences_summary"] = f"Preferences truncated ({len(prefs)} fields)"
            print(f"⚠️ Truncated preferences: total length {total_len} chars")

    return state


def save_working_state(connection_id: str, state: Dict[str, Any]) -> None:
    """
    Persist the agent's current working memory (e.g., preferences, cars, ratings)
    after truncating large fields to prevent oversized DynamoDB entries.
    """
    try:
        safe_state = _truncate_state(state)
        table.update_item(
            Key={"connectionId": connection_id},
            UpdateExpression="SET working_state = :s",
            ExpressionAttributeValues={":s": safe_state},
        )
    except Exception as e:
        print(f"❌ Error saving working state: {e}")

# def save_working_state(connection_id, state):
#     """Persist the agent's current working memory (e.g. preferences, cars, ratings)."""
#     try:
#         table.update_item(
#             Key={"connectionId": connection_id},
#             UpdateExpression="SET working_state = :s",
#             ExpressionAttributeValues={":s": state},
#         )
#     except Exception as e:
#         print(f"Error saving working state: {e}")

def build_history_messages(connection_id: str) -> List[Dict[str, Any]]:
    raw = get_session_messages(connection_id) or []
    msgs: List[Dict[str, Any]] = []
    for m in raw:
        role = m.get("role")
        content = m.get("content")
        if role in ("user", "assistant") and isinstance(content, str):
            msgs.append({"role": role, "content": [{"text": content}]})
    return msgs