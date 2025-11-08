# tools/fetch_safety_ratings.py
import os, json, boto3, requests
from typing import Dict, List, Any

SPEC = {
    "toolSpec": {
        "name": "fetch_safety_ratings",
        "description": (
            "Retrieve NHTSA 5-Star safety ratings for a specific vehicle "
            "by make, model, and year."
        ),
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "year": {"type": "integer", "description": "Model year (e.g., 2020)"},
                    "make": {"type": "string", "description": "Vehicle make (e.g., Honda)"},
                    "model": {"type": "string", "description": "Vehicle model (e.g., Civic)"}
                },
                "required": ["year", "make", "model"],
                "additionalProperties": False
            }
        }
    }
}


def _fetch_safety_rating(year: int, make: str, model: str) -> Dict[str, Any]:
    """Query the NHTSA Safety Ratings API for the given year/make/model."""
    base_url = f"https://api.nhtsa.gov/SafetyRatings/modelyear/{year}/make/{make}/model/{model}?format=json"

    try:
        resp = requests.get(base_url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"Error fetching safety rating: {e}")
        return {"error": str(e)}

    results = data.get("Results", [])
    if not results:
        return {"error": "No safety data found."}

    # Many models have multiple trims — we’ll take all with their key metrics
    ratings = []
    for r in results:
        ratings.append({
            "VehicleDescription": r.get("VehicleDescription"),
            "OverallRating": r.get("OverallRating"),
            "OverallFrontCrashRating": r.get("OverallFrontCrashRating"),
            "OverallSideCrashRating": r.get("OverallSideCrashRating"),
            "RolloverRating": r.get("RolloverRating"),
            "VehicleId": r.get("VehicleId")
        })

    return {
        "year": year,
        "make": make,
        "model": model,
        "count": len(ratings),
        "ratings": ratings
    }


def handle(connection_id: str, tool_input: Dict) -> List[Dict]:
    """Main Bedrock-style tool handler."""
    year = tool_input.get("year")
    make = tool_input.get("make")
    model = tool_input.get("model")

    if not (year and make and model):
        return [{"text": "Error: Missing 'year', 'make', or 'model'."}]

    result = _fetch_safety_rating(int(year), make, model)
    return [{"json": result}]
