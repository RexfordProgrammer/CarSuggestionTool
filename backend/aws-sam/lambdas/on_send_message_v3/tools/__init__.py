from tools import fetch_user_preferences

ALL_TOOLS = [fetch_user_preferences]

def tool_specs():
    # Return tool specs
    return [t.SPEC["toolSpec"] for t in ALL_TOOLS]

def dispatch(name: str, connection_id: str, tool_input: dict):
    # dispatch a tool
    for t in ALL_TOOLS:
        if name == t.SPEC["toolSpec"]["name"]:
            return t.handle(connection_id, tool_input)
    raise ValueError(f"Unknown tool: {name}")
