import requests
import json
from typing import Dict, List, Any

# Assuming these Pydantic models are imported from a module like 'pydantic_models'
# For this script, we'll define the necessary ones inline for completeness.
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Union

# --- NECESSARY PYDANTIC IMPORTS (for local context) ---
class JsonContent(BaseModel):
    """The JSON payload for a tool result."""
    json: Dict[str, Any]

class ToolInputSchema(BaseModel):
    """Models the 'inputSchema' part of the tool specification."""
    # Using alias for schema compatibility with 'json' key
    json: Dict[str, Any] = Field(..., alias="json") 

class ToolSpec(BaseModel):
    """The core specification for a single tool."""
    name: str
    description: str
    inputSchema: ToolInputSchema

class FullToolSpec(BaseDict):
    """Models the complete SPEC object required by the tool modules (t.SPEC)."""
    toolSpec: ToolSpec

# --- TOOL SPECIFICATION REMAINS THE SAME ---
SPEC = FullToolSpec(
    toolSpec=ToolSpec(
        name="fetch_all_makes",
        description=(
            "Retrieve a list of all vehicle manufacturers (makes) from the NHTSA database. "
            "This tool does not require any input. Use it when you need to validate or display "
            "the available makes before calling other tools like `fetch_cars_of_year`."
        ),
        inputSchema=ToolInputSchema(
            json={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            }
        )
    )
).model_dump(by_alias=True) # Use model_dump to serialize the Pydantic model back to the expected dict structure

# --- HELPER FUNCTION (NO CHANGE) ---
def _fetch_all_makes() -> List[Dict[str, Any]]:
    """Fetch all registered vehicle makes from NHTSA."""
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

# --- MODIFIED HANDLER FUNCTION ---
def handle(connection_id: str, tool_input: Dict) -> List[JsonContent]:
    """
    Handler function for Bedrock tool orchestration.
    Returns a List of Pydantic JsonContent blocks.
    """
    makes = _fetch_all_makes()
    
    # 1. Create the structured data dictionary
    response_data = {
        "count": len(makes),
        "makes": makes[:40],  # Limit for readability
    }
    
    # 2. Wrap the data in the JsonContent Pydantic model
    json_content_block = JsonContent(json=response_data)
    
    # 3. Return a list containing the Pydantic content block
    return [json_content_block]

# Note: The 'ToolResult' model in your orchestrator expects content: List[JsonContent | TextContentBlock].
# By returning List[JsonContent] here, you satisfy that requirement directly.