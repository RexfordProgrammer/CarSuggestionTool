# tools/__init__.py
from typing import Any, Dict
from tools import (
    extract_user_prefs,
    fetch_cars_of_year,
    fetch_gas_milage,
    fetch_safety_ratings,
)

# List of imported tool modules (each must define SPEC and handle())
ALL_TOOLS = [
    fetch_cars_of_year,
    fetch_gas_milage,
    fetch_safety_ratings,
    extract_user_prefs,
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


def allowed_tools() -> Dict[str, Any]:
    specs = tool_specs() or []
    tool_config = {"tools": [{"toolSpec": s} for s in specs]} if specs else None
    allowed_names = {s.get("name") for s in specs}
    return {"tool_config": tool_config, "allowed_names": allowed_names, "specs": specs}