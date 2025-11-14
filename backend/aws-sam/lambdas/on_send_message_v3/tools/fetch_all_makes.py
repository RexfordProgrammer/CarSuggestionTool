import requests
from typing import Dict, List, Any

from pydantic_models import (
    JsonContent,
    ToolResult,
    ToolResultContentBlock,
    ToolInputSchema,
    ToolSpec,
    FullToolSpec
)

# ────────────────────────────────────────────────────────────────────────────────
# TOOL SPEC (converted to Pydantic)
# ────────────────────────────────────────────────────────────────────────────────
SPEC = FullToolSpec(
    toolSpec=ToolSpec(
        name="fetch_all_makes",
        description=(
            "Retrieve a list of all vehicle manufacturers (makes) from the NHTSA "
            "database. This tool does not require inputs."
        ),
        inputSchema=ToolInputSchema(
            json={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            }
        ),
    )
).model_dump(by_alias=True)


# ────────────────────────────────────────────────────────────────────────────────
# Helper — returns list of {"Make_ID", "Make_Name"}
# ────────────────────────────────────────────────────────────────────────────────
def _fetch_all_makes() -> List[Dict[str, Any]]:
    url = "https://vpic.nhtsa.dot.gov/api/vehicles/GetAllMakes?format=json"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()

        data = resp.json()
        results = data.get("Results", [])

        return [
            {
                "Make_ID": r.get("Make_ID"),
                "Make_Name": r.get("Make_Name"),
            }
            for r in results
        ]

    except Exception as e:
        print(f"Error fetching makes from NHTSA: {e}")
        return []


# ────────────────────────────────────────────────────────────────────────────────
# TOOL ENTRYPOINT — Always returns ToolResultContentBlock
# ────────────────────────────────────────────────────────────────────────────────
def handle(connection_id: str, tool_input: Dict[str, Any], tool_use_id: str) -> ToolResultContentBlock:
    """
    Retrieve all vehicle makes from NHTSA and ALWAYS return ToolResultContentBlock.
    """

    makes = _fetch_all_makes()

    # If API failure produced an empty list, still report that cleanly
    response_data = {
        "count": len(makes),
        "makes": makes[:40],  # cap for readability
    }

    jc = JsonContent(json=response_data)

    return ToolResultContentBlock(
        toolResult=ToolResult(
            toolUseId=tool_use_id,
            content=[jc]
        )
    )
