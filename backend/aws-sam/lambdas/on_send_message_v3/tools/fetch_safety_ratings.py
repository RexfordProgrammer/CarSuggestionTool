# tools/fetch_safety_ratings.py
import requests
from typing import Dict, List, Any, Union

from pydantic_models import (ToolResultContentBlock, TextContentBlock,
                             JsonContent, ToolResult,
                             ToolInputSchema, ToolSpec, FullToolSpec)


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

def handle(connection_id: str, tool_input: Dict[str, Any], tool_use_id: str) -> ToolResultContentBlock:
    """
    Handle safety rating lookup and ALWAYS return a ToolResultContentBlock.
    """

    year  = tool_input.get("year")
    make  = tool_input.get("make")
    model = tool_input.get("model")

    # ---------------------------
    # 1. Input Validation
    # ---------------------------
    if not (year and make and model):
        tb = TextContentBlock(text="Error: Missing 'year', 'make', or 'model'.")
        return ToolResultContentBlock(
            toolResult=ToolResult(
                toolUseId=tool_use_id,
                content=[tb]
            )
        )

    # ---------------------------
    # 2. Try execution
    # ---------------------------
    try:
        result = _fetch_safety_rating(int(year), make, model)
    except Exception as e:
        tb = TextContentBlock(text=f"Unexpected failure while querying safety ratings: {e}")
        return ToolResultContentBlock(
            toolResult=ToolResult(
                toolUseId=tool_use_id,
                content=[tb]
            )
        )

    # ---------------------------
    # 3. Structured-error case
    # ---------------------------
    if isinstance(result, dict) and "error" in result:
        tb = TextContentBlock(text=f"Safety rating retrieval failed: {result['error']}")
        return ToolResultContentBlock(
            toolResult=ToolResult(
                toolUseId=tool_use_id,
                content=[tb]
            )
        )

    # ---------------------------
    # 4. SUCCESS — Always JsonContent
    # ---------------------------
    jc = JsonContent(json=result)

    return ToolResultContentBlock(
        toolResult=ToolResult(
            toolUseId=tool_use_id,
            content=[jc]
        )
    )