from typing import Dict, List, Any, Union
import requests

from pydantic_input_comps import (ToolResult,JsonContent,ToolInputSchema
                                  ,ToolSpec,FullToolSpec)
from pydantic_models import (ToolResultContentBlock, TextContentBlock)

def prompt():
    """Returns Tool Specific Prompt""" 
    p = "reduce to a plain, not numbered, list of 10 makes and models and years"
    return p

# ────────────────────────────────────────────────────────────────────────────────
# Bedrock tool spec (converted to Pydantic)
# ────────────────────────────────────────────────────────────────────────────────
SPEC = FullToolSpec(
    toolSpec=ToolSpec(
        name="fetch_models_of_make_year",
        description="Used to get models of a particular make from a particular year",
        inputSchema=ToolInputSchema(
            json={
                "type": "object",
                "properties": {
                    "year": {"type": "integer"},
                    "make": {"type": "string"},
                },
                "required": ["year"],
                "additionalProperties": False,
            }
        ),
    )
).model_dump(by_alias=True)


# ────────────────────────────────────────────────────────────────────────────────
# Helper — returns list OR {"error": "..."}
# ────────────────────────────────────────────────────────────────────────────────
def _fetch_from_nhtsa(
    year: int, make: str = "Toyota"
) -> Union[List[Dict[str, Any]], Dict[str, str]]:
    """
    Fetch models for a given make/year.
    Returns:
      - List of dicts (success)
      - {"error": "..."} on failure
    """

    url = (
        f"https://vpic.nhtsa.dot.gov/api/vehicles/"
        f"GetModelsForMakeYear/make/{make}/modelyear/{year}?format=json"
    )

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()

        data = resp.json()
        results = data.get("Results", []) or []

        return [
            {
                "Make_Name": r.get("Make_Name"),
                "Model_Name": r.get("Model_Name"),
            }
            for r in results
            if r.get("Model_Name")
        ]

    except Exception as e: #pylint: disable=broad-exception-caught
        print(f"Error fetching data from NHTSA: {e}")
        return {"error": str(e)}


# ────────────────────────────────────────────────────────────────────────────────
# TOOL ENTRYPOINT — Always returns ToolResultContentBlock
# ────────────────────────────────────────────────────────────────────────────────
def handle(connection_id: str, tool_input: Dict[str, Any],
           tool_use_id: str) -> ToolResultContentBlock:#pylint disable:unused-argument
    """
    Fetch models for a given make/year and ALWAYS return a ToolResultContentBlock.
    """
    year = tool_input.get("year")
    make = tool_input.get("make", "Toyota")

    # 1. Validate input
    if not year:
        tb = TextContentBlock(text="Error: Missing required input 'year'.")
        return ToolResultContentBlock(
            toolResult=ToolResult(toolUseId=tool_use_id, content=[tb])
        )

    try:
        year_int = int(year)
    except ValueError:
        tb = TextContentBlock(text="Error: 'year' must be an integer.")
        return ToolResultContentBlock(
            toolResult=ToolResult(toolUseId=tool_use_id, content=[tb])
        )

    # 2. Fetch data
    result = _fetch_from_nhtsa(year_int, make)

    # 3. Error from API or connection issue
    if isinstance(result, dict) and "error" in result:
        tb = TextContentBlock(text=f"NHTSA API call failed: {result['error']}")
        return ToolResultContentBlock(
            toolResult=ToolResult(toolUseId=tool_use_id, content=[tb])
        )

    cars: List[Dict[str, Any]] = result

    # 4. No cars found
    if not cars:
        jc = JsonContent(
            json={
                "year": year_int,
                "make": make,
                "count": 0,
                "vehicles": [],
                "message": f"No models found for make='{make}' in year={year_int}.",
            }
        )
        return ToolResultContentBlock(
            toolResult=ToolResult(toolUseId=tool_use_id, content=[jc])
        )

    # 5. Normal success
    jc = JsonContent(
        json={
            "year": year_int,
            "make": make,
            "count": len(cars),
            "vehicles": cars[:100],  # consistent with your original capping
        }
    )

    return ToolResultContentBlock(
        toolResult=ToolResult(toolUseId=tool_use_id, content=[jc])
    )
