import requests
from typing import Dict, List, Any, Union
from pydantic import BaseModel, Field

# Assuming these Pydantic models are imported from a module like 'pydantic_models'
# NOTE: In a real system, you would only import these from a central file.
class TextContentBlock(BaseModel):
    """A simple text block."""
    text: str

class JsonContent(BaseModel):
    """The JSON payload for a tool result."""
    json: Dict[str, Any]

class ToolInputSchema(BaseModel):
    """Models the 'inputSchema' part of the tool specification."""
    json: Dict[str, Any] = Field(..., alias="json") 

class ToolSpec(BaseModel):
    """The core specification for a single tool."""
    name: str
    description: str
    inputSchema: ToolInputSchema

class FullToolSpec(BaseModel):
    """Models the complete SPEC object required by the tool modules (t.SPEC)."""
    toolSpec: ToolSpec
    
# Define the consistent return type for the handle function
HandleReturnType = List[Union[JsonContent, TextContentBlock]]


# ────────────────────────────────────────────────────────────────────────────────
# Bedrock tool spec (Converted to Pydantic and dumped back)
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
# Helper function (Modified to signal failure via a Dict)
# ────────────────────────────────────────────────────────────────────────────────
def _fetch_from_nhtsa(year: int, make: str = "Toyota") -> Union[List[Dict[str, Any]], Dict[str, str]]:
    """
    Fetch models for a given make/year. Returns list of models on success, 
    or a dictionary with an 'error' key on failure.
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

        # Only keep Make_Name and Model_Name, NEVER Model_ID
        return [
            {
                "Make_Name": r.get("Make_Name"),
                "Model_Name": r.get("Model_Name"),
            }
            for r in results
            if r.get("Model_Name")
        ]
    except Exception as e:
        print(f"Error fetching data from NHTSA: {e}")
        return {"error": str(e)} # Return error dict


# ────────────────────────────────────────────────────────────────────────────────
# Bedrock tool entry-point (MODIFIED)
# ────────────────────────────────────────────────────────────────────────────────
def handle(connection_id: str, tool_input: Dict) -> HandleReturnType:
    """
    Handler function for Bedrock tool orchestration.
    Returns a List of Pydantic JsonContent or TextContentBlock.
    """
    year = tool_input.get("year")
    make = tool_input.get("make", "Toyota")
    
    # Simple input validation, although the API handles year typing.
    if not year:
        return [TextContentBlock(text="Error: Missing required input 'year'.")]

    try:
        year_int = int(year)
    except ValueError:
        return [TextContentBlock(text="Error: 'year' must be an integer.")]

    # Fetch data
    cars_result = _fetch_from_nhtsa(year_int, make)
    
    # 1. Check for API/network failure
    if isinstance(cars_result, dict) and "error" in cars_result:
        error_msg = f"NHTSA API call failed: {cars_result['error']}"
        return [TextContentBlock(text=error_msg)]

    # 2. Assign the successful result list
    cars: List[Dict[str, Any]] = cars_result

    if not cars:
        # Explicit “no results” case (structured data)
        response_data = {
            "year": year_int,
            "make": make,
            "count": 0,
            "vehicles": [],
            "message": f"No models found for make='{make}' in year={year_int}.",
        }
        return [JsonContent(json=response_data)]

    # 3. Normal case (structured data)
    response_data = {
        "year": year_int,
        "make": make,
        "count": len(cars),
        "vehicles": cars[:100],  # still capped at 100
    }
    return [JsonContent(json=response_data)]