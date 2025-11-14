# tools/fetch_safety_ratings.py
import requests
from typing import Dict, List, Any, Union

# Assuming these Pydantic models are imported from a module like 'pydantic_models'
from pydantic import BaseModel, Field # We'll assume these are available
# from pydantic_models import TextContentBlock, JsonContent # Assume this for real life

# --- NECESSARY PYDANTIC MODELS (for local context) ---
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
# Bedrock tool spec
# ────────────────────────────────────────────────────────────────────────────────
# Convert the dictionary SPEC into a Pydantic model and then dump it back 
# to ensure it's structurally correct before being used by the tool loader.
SPEC = FullToolSpec(
    toolSpec=ToolSpec(
        name="fetch_safety_ratings",
        description=("Get NHTSA crash-test ratings (overall, front, side, rollover) "
                     "for a specific {year, make, model}. Retries ±1 year if the "
                     "exact year has no published data."),
        inputSchema=ToolInputSchema(
            json={
                "type": "object",
                "properties": {
                    "year":  {"type": "integer", "description": "Model year (e.g., 2020)"},
                    "make":  {"type": "string",  "description": "Make (e.g., Ford)"},
                    "model": {"type": "string",  "description": "Model (e.g., Ranger)"}
                },
                "required": ["year", "make", "model"],
                "additionalProperties": False
            }
        )
    )
).model_dump(by_alias=True)

# ────────────────────────────────────────────────────────────────────────────────
# Core helpers (UNCHANGED)
# ────────────────────────────────────────────────────────────────────────────────
def _query_summary(year: int, make: str, model: str) -> List[Dict[str, Any]]:
    """Call the summary endpoint and return its Results list (may be empty)."""
    url = (
        f"https://api.nhtsa.gov/SafetyRatings/modelyear/{year}"
        f"/make/{make}/model/{model}?format=json"
    )
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json().get("Results", [])


def _query_vehicle_detail(vehicle_id: int) -> Dict[str, Any]:
    """Return the first (and only) result for a specific VehicleId."""
    url = f"https://api.nhtsa.gov/SafetyRatings/VehicleId/{vehicle_id}?format=json"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    all_results = resp.json().get("Results", [])
    return all_results[0] if all_results else {}


def _fetch_safety_rating(year: int, make: str, model: str) -> Dict[str, Any]:
    """
    Fetch ratings for {year, make, model}.
    If the exact year is empty, retry (year+1) then (year-1).
    """
    # ... (body of this function is unchanged, it returns a Dict[str, Any])
    
    results = _query_summary(year, make, model)

    if not results:
        for alt in (year + 1, year - 1):
            try:
                results = _query_summary(alt, make, model)
            except Exception:
                results = []
            if results:
                year = alt
                break

    if not results:
        return {
            "year": year,
            "make": make,
            "model": model,
            "count": 0,
            "ratings": [],
            "note": "NHTSA has no published safety data for this model/year."
        }

    ratings: List[Dict[str, Any]] = []
    for r in results:
        vid  = r.get("VehicleId")
        desc = r.get("VehicleDescription", "")

        # Defensive check
        if not vid:
            continue

        try:
            detail = _query_vehicle_detail(vid)
        except Exception as e:
            detail = {}
            detail["error"] = f"Failed to fetch VehicleId {vid}: {e}"

        ratings.append({
            "VehicleDescription": desc,
            "VehicleId": vid,
            "OverallRating": detail.get("OverallRating"),
            "OverallFrontCrashRating": detail.get("OverallFrontCrashRating"),
            "OverallSideCrashRating": detail.get("OverallSideCrashRating"),
            "RolloverRating": detail.get("RolloverRating"),
            "SidePoleCrashRating": detail.get("SidePoleCrashRating"),
            "SideBarrierRatingOverall": detail.get("SideBarrierRatingOverall"),
        })

    return {
        "year": year,
        "make": make,
        "model": model,
        "count": len(ratings),
        "ratings": ratings
    }

# ────────────────────────────────────────────────────────────────────────────────
# Bedrock tool entry-point (MODIFIED)
# ────────────────────────────────────────────────────────────────────────────────
def handle(connection_id: str, tool_input: Dict[str, Any]) -> HandleReturnType:
    """
    Bedrock-style wrapper.
    Returns a list containing a Pydantic JsonContent (on success) or
    TextContentBlock (on error).
    """
    year  = tool_input.get("year")
    make  = tool_input.get("make")
    model = tool_input.get("model")

    # 1. Input Validation (returns TextContentBlock on error)
    if not (year and make and model):
        return [TextContentBlock(text="Error: Missing 'year', 'make', or 'model'.")]

    try:
        # 2. Fetch the rating, handles internal retries
        result = _fetch_safety_rating(int(year), make, model)
    except Exception as e:
        # 3. Handle unexpected API failure (e.g., network error, DNS)
        error_msg = f"Unexpected failure while querying safety ratings: {e}"
        return [TextContentBlock(text=error_msg)]

    # 4. Check for a structured error message placed by the helper function
    if "error" in result:
        error_msg = f"Safety rating retrieval failed: {result['error']}"
        return [TextContentBlock(text=error_msg)]

    # 5. Successful Result or No Data Found Note (returns JsonContent)
    # The _fetch_safety_rating function guarantees a structured dictionary
    # even when no data is found (with a "note" field).
    return [JsonContent(json=result)]