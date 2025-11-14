# tools/__init__.py
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from pydantic_models import JsonContent, TextContentBlock, ToolConfig, ToolSpecsOutput, FullToolSpec, ToolConfigItem

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

def _normalize_blocks(blocks):
    normalized = []
    for b in blocks:
        if isinstance(b, JsonContent) or isinstance(b, TextContentBlock):
            normalized.append(b)
        elif isinstance(b, dict) and "json" in b:
            normalized.append(JsonContent(json=b["json"]))
        elif isinstance(b, str):
            normalized.append(TextContentBlock(text=b))
        else:
            # last resort - stringify
            normalized.append(TextContentBlock(text=str(b)))
    return normalized

def dispatch(name: str, connection_id: str, tool_input: dict):
    for t in ALL_TOOLS:
        if name == t.SPEC["toolSpec"]["name"]:
            raw = t.handle(connection_id, tool_input)
            if not isinstance(raw, list):
                raw = [raw]
            return _normalize_blocks(raw)

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