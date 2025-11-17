"""This fine is the package declaration of tools"""
# TODO: Refactoring here would probably be ensuring all tools respond never as as dict
## then removing the dict option as a dict return object in the declations of pydantic models 

from typing import List
from pydantic_input_comps import (
    ToolSpecsBundle,
    FullToolSpec,
    ToolConfigItem,
)
from pydantic_models import (
    ToolConfig,
    ToolResultContentBlock,
)

from . import (
    fetch_models_of_make_year,
    fetch_gas_mileage,
    fetch_safety_ratings,
    fetch_price_of_car
)

ALL_TOOLS = [
    fetch_models_of_make_year,
    fetch_gas_mileage,
    fetch_safety_ratings,
    fetch_price_of_car
]

from small_model_api_summarizer import create_summary_result_block

### Name dedupe
_tool_names: List[str] = [t.SPEC["toolSpec"]["name"] for t in ALL_TOOLS]
if len(_tool_names) != len(set(_tool_names)):
    raise RuntimeError(f"Duplicate tool names detected: {_tool_names}")


def tool_specs() -> List[FullToolSpec]:
    """Gathers Tool Specs as List[FullToolSpec]"""
    return [FullToolSpec.model_validate(t.SPEC) for t in ALL_TOOLS]


def dispatch(name: str, connection_id: str,
             tool_input: dict, tool_use_id: str, bedrock,debug = True) -> ToolResultContentBlock:
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
    if debug:
        print ("\n[No summary]", original_tool_result_block.toolResult.content)

    summarized_tool: ToolResultContentBlock = create_summary_result_block(bedrock,
                                                                         original_tool_result_block,
                                                                         executed_tool.prompt())

    return summarized_tool

def output_tool_specs() -> ToolSpecsBundle:
    """Bundles the Tool Specs into a single returned object"""
    validated_specs: List[FullToolSpec] = [
        FullToolSpec.model_validate(t.SPEC) for t in ALL_TOOLS
    ]

    tool_config_items = [
        ToolConfigItem(toolSpec=spec.toolSpec)
        for spec in validated_specs
    ]

    return ToolSpecsBundle(
        tool_config=ToolConfig(tools=tool_config_items),
        specs=[spec.model_dump(by_alias=True) for spec in validated_specs],
    )
