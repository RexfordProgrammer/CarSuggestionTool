# tools/__init__.py
from tools import (
    fetch_user_preferences,
    fetch_cars_of_year,
    fetch_gas_milage,
    fetch_safety_rating,
)

# List of imported tool modules (each must define SPEC and handle())
ALL_TOOLS = [
    fetch_user_preferences,
    fetch_cars_of_year,
    fetch_gas_milage,
    fetch_safety_rating,
]


def tool_specs():
    """Return all tool specs for Bedrock registration."""
    return [t.SPEC["toolSpec"] for t in ALL_TOOLS]


def dispatch(name: str, connection_id: str, tool_input: dict):
    """Dispatch a tool call by name."""
    for t in ALL_TOOLS:
        if name == t.SPEC["toolSpec"]["name"]:
            return t.handle(connection_id, tool_input)
    raise ValueError(f"Unknown tool: {name}")
