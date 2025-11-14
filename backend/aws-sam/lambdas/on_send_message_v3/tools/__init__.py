# tools/__init__.py
from typing import List
from pydantic_models import (
    ToolConfig,
    ToolSpecsOutput,
    FullToolSpec,
    ToolConfigItem,
    ToolResultContentBlock
)

from . import (
    fetch_models_of_make_year,
    fetch_gas_mileage,
    fetch_safety_ratings,
    fetch_all_makes,   # ← don't forget to add this to ALL_TOOLS
)

ALL_TOOLS = [
    fetch_models_of_make_year,
    fetch_gas_mileage,
    fetch_safety_ratings,
    fetch_all_makes,
]

import threading


# ---------------------------------------------------------------------
# Sanity check for duplicate names
# ---------------------------------------------------------------------
_tool_names: List[str] = [t.SPEC["toolSpec"]["name"] for t in ALL_TOOLS]
if len(_tool_names) != len(set(_tool_names)):
    raise RuntimeError(f"Duplicate tool names detected: {_tool_names}")


# ---------------------------------------------------------------------
# Load specs as Pydantic objects
# ---------------------------------------------------------------------
def tool_specs() -> List[FullToolSpec]:
    return [FullToolSpec.model_validate(t.SPEC) for t in ALL_TOOLS]


# ---------------------------------------------------------------------
# Dispatcher — now passes tool_use_id and expects a ToolResultContentBlock
# ---------------------------------------------------------------------
def dispatch(name: str, connection_id: str, tool_input: dict, tool_use_id: str) -> ToolResultContentBlock:
    """
    Dispatch a tool by exact name.
    Each tool now always returns a ToolResultContentBlock.
    """
    for t in ALL_TOOLS:
        if name == t.SPEC["toolSpec"]["name"]:
            return t.handle(connection_id, tool_input, tool_use_id)

    raise ValueError(f"Unknown tool: {name}")


# ---------------------------------------------------------------------
# Convert specs into the shape Bedrock expects
# ---------------------------------------------------------------------
def tool_specs_output() -> ToolSpecsOutput:
    validated_specs: List[FullToolSpec] = [
        FullToolSpec.model_validate(t.SPEC) for t in ALL_TOOLS
    ]

    tool_config_items = [
        ToolConfigItem(toolSpec=spec.toolSpec)
        for spec in validated_specs
    ]

    return ToolSpecsOutput(
        tool_config=ToolConfig(tools=tool_config_items),
        specs=[spec.model_dump(by_alias=True) for spec in validated_specs],
    )

class ToolCall:
    def __init__(self, name: str, connection_id: str, tool_input: dict, tool_use_id: str):
        self.name = name
        self.connection_id = connection_id
        self.tool_input = tool_input
        self.tool_use_id = tool_use_id
        self.thread_obj = threading.Thread(target=self.call_tool, args=())
        self.tool_response = None

    def start_thread(self):
        self.thread_obj.start()
       
    def call_tool(self):
        self.tool_response = dispatch(self.name, self.connection_id, self.tool_input, self.tool_use_id)
        