# tools/fetch_safety_ratings.py
import requests
from typing import Dict, List, Any

# ────────────────────────────────────────────────────────────────────────────────
# Bedrock tool spec
# ────────────────────────────────────────────────────────────────────────────────
SPEC = {
    "toolSpec": {
        "name": "fetch_safety_ratings",
        "description": "Get NHTSA crash-test ratings (overall, front, side, rollover) "
                       "for a specific {year, make, model}. Retries ±1 year if the "
                       "exact year has no published data.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "year":  {"type": "integer", "description": "Model year (e.g., 2020)"},
                    "make":  {"type": "string",  "description": "Make (e.g., Ford)"},
                    "model": {"type": "string",  "description": "Model (e.g., Ranger)"}
                },
                "required": ["year", "make", "model"],
                "additionalProperties": False
            }
        }
    }
}

# ────────────────────────────────────────────────────────────────────────────────
# Core helpers
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
# Bedrock tool entry-point
# ────────────────────────────────────────────────────────────────────────────────
def handle(connection_id: str, tool_input: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Bedrock-style wrapper.
    Returns a list containing a single JSON block so the orchestrator can
    drop it directly into a `toolResult`.
    """
    year  = tool_input.get("year")
    make  = tool_input.get("make")
    model = tool_input.get("model")

    if not (year and make and model):
        return [{"text": "Error: Missing 'year', 'make', or 'model'."}]

    try:
        result = _fetch_safety_rating(int(year), make, model)
    except Exception as e:
        result = {"error": f"Unexpected failure: {e}"}

    return [{"json": result}]
