# tools/__init__.py
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from pydantic_models import ToolConfig, ToolSpecsOutput, FullToolSpec, ToolConfigItem

from . import (
    fetch_models_of_make_year,
    fetch_gas_mileage,
    fetch_safety_ratings,
)

ALL_TOOLS = [
    fetch_models_of_make_year,
    fetch_gas_mileage,
    fetch_safety_ratings,
]

# sanity check for duplicate names - Now uses validated data
_tool_names: List[str] = [t.SPEC["toolSpec"]["name"] for t in ALL_TOOLS]
if len(_tool_names) != len(set(_tool_names)):
    raise RuntimeError(f"Duplicate tool names detected: {_tool_names}")


#TODO REDUCE DUPLICATION OF EFFORTS
def tool_specs() -> List[FullToolSpec]:
    """
    Return Bedrock tool config + raw specs for prompts/UX as a Pydantic model.
    """
    validated_specs: List[FullToolSpec] = [
        FullToolSpec.model_validate(t.SPEC) for t in ALL_TOOLS
    ]
    return validated_specs

def dispatch(name: str, connection_id: str, tool_input: dict) -> Any:
    """Dispatch a tool call by exact toolSpec.name."""
    for t in ALL_TOOLS:
        if name == t.SPEC["toolSpec"]["name"]:
            # NOTE: We rely on the tool module's handle function to be correct.
            # TODO: optionally use a Pydantic model to validate tool_input here.
            return t.handle(connection_id, tool_input)
            
    raise ValueError(f"Unknown tool: {name}")


def tool_specs_output() -> ToolSpecsOutput:
    """
    Return Bedrock tool config + raw specs for prompts/UX as a Pydantic model.
    """
    validated_specs: List[FullToolSpec] = [
        FullToolSpec.model_validate(t.SPEC) for t in ALL_TOOLS
    ]
    tool_config_items = [
        ToolConfigItem(
            toolSpec=spec.toolSpec # Already a Pydantic ToolSpec object
        )
        for spec in validated_specs
    ]
    return ToolSpecsOutput(
        tool_config=ToolConfig(tools=tool_config_items),
        
        specs=[spec.model_dump(by_alias=True) for spec in validated_specs],
    )