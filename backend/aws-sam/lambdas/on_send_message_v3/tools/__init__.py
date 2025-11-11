# tools/__init__.py
from typing import Any, Dict, List

# ✅ Use relative imports inside the package
from . import (
    fetch_cars_of_year,
    fetch_gas_mileage,      # make sure the tool module is named with "_mileage"
    fetch_safety_ratings,
)

# Each module must expose: SPEC: {"toolSpec": {...}}, and handle(connection_id, input)
ALL_TOOLS = [
    fetch_cars_of_year,
    fetch_gas_mileage,
    fetch_safety_ratings,
]

# (Optional) sanity check for duplicate names
_tool_names: List[str] = [t.SPEC["toolSpec"]["name"] for t in ALL_TOOLS]
if len(_tool_names) != len(set(_tool_names)):
    raise RuntimeError(f"Duplicate tool names detected: {_tool_names}")

def tool_specs() -> Dict[str, Any]:
    """Return Bedrock tool config + raw specs for prompts/UX."""
    specs = [t.SPEC for t in ALL_TOOLS]  # each is {"toolSpec": {...}}
    tool_config = {
        "tools": [
            {"toolSpec": spec["toolSpec"]}
            for spec in specs
        ]
    }
    return {
        "tool_config": tool_config,
        "specs": specs,
    }

def dispatch(name: str, connection_id: str, tool_input: dict) -> Any:
    """Dispatch a tool call by exact toolSpec.name."""
    for t in ALL_TOOLS:
        if name == t.SPEC["toolSpec"]["name"]:
            return t.handle(connection_id, tool_input)
    raise ValueError(f"Unknown tool: {name}")
