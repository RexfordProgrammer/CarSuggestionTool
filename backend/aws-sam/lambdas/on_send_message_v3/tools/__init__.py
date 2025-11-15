# tools/__init__.py
from typing import List
from pydantic_models import (
    ToolConfig,
    ToolSpecsOutput,
    FullToolSpec,
    ToolConfigItem,
    ToolResultContentBlock,ToolResult,TextContentBlock
)

from . import (
    fetch_models_of_make_year,
    fetch_gas_mileage,
    fetch_safety_ratings,
    # fetch_all_makes,   # ← don't forget to add this to ALL_TOOLS
)

ALL_TOOLS = [
    fetch_models_of_make_year,
    fetch_gas_mileage,
    fetch_safety_ratings,
    # fetch_all_makes,
]

import threading
from small_model_api_summarizer import create_summary_result_block

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
    """Gathers Tool Specs as List[FullToolSpec]"""
    return [FullToolSpec.model_validate(t.SPEC) for t in ALL_TOOLS]


# ---------------------------------------------------------------------
# Dispatcher — now passes tool_use_id and expects a ToolResultContentBlock
# ---------------------------------------------------------------------
def dispatch(name: str, connection_id: str, 
             tool_input: dict, tool_use_id: str, bedrock) -> ToolResultContentBlock:
    """
    Dispatch a tool by its exact name, execute it, and optionally summarize the result.
    Always returns a ToolResultContentBlock.
    """
    executed_tool = None
    for t in ALL_TOOLS:
        if name == t.SPEC["toolSpec"]["name"]:
            executed_tool = t
            break

    if executed_tool is None:
        raise ValueError(f"Unknown tool: {name}")

    original_tool_result_block: ToolResultContentBlock = executed_tool.handle(
        connection_id,
        tool_input,
        tool_use_id
    )
    
    summarized_tool: ToolResultContentBlock  = create_summary_result_block(bedrock, original_tool_result_block, 
                                                  executed_tool.prompt())

    return summarized_tool


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
    def __init__(self, name: str, connection_id: str, tool_input: dict, tool_use_id: str, bedrock):
        self.name = name
        self.connection_id = connection_id
        self.tool_input = tool_input
        self.tool_use_id = tool_use_id
        self.thread_obj = threading.Thread(target=self.call_tool, args=())
        self.tool_response = None
        self.bedrock=bedrock

    def start_thread(self):
        self.thread_obj.start()
       
    def call_tool(self):
        self.tool_response = dispatch(self.name, self.connection_id, self.tool_input, self.tool_use_id,self.bedrock)
        