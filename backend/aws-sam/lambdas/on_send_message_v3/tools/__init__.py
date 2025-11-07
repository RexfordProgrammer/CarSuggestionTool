from tools import fetch_user_preferences

# Register all tools here
ALL_TOOLS = [fetch_user_preferences]

def tool_specs():
    """Return the list of toolSpec dicts for all tools."""
    return [t.SPEC["toolSpec"] for t in ALL_TOOLS]

def dispatch(name: str, connection_id: str, tool_input: dict):
    """Dispatch tool calls by name."""
    for t in ALL_TOOLS:
        if name == t.SPEC["toolSpec"]["name"]:
            return t.handle(connection_id, tool_input)
    raise ValueError(f"Unknown tool: {name}")
