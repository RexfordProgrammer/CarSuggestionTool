# tools/fetch_safety_ratings.py
import requests
from typing import Dict, List, Any
import json 

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
    """Query the NHTSA Safety Ratings API and resolve each VehicleId to get full ratings."""
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

    ratings = []
    for r in results:
        vid = r.get("VehicleId")
        desc = r.get("VehicleDescription")

        if not vid:
            continue

        # ✅ Fetch full rating details for each vehicle ID
        try:
            detail_resp = requests.get(f"https://api.nhtsa.gov/SafetyRatings/VehicleId/{vid}?format=json", timeout=10)
            detail_resp.raise_for_status()
            detail_data = detail_resp.json()
            full_info = detail_data.get("Results", [{}])[0]
        except Exception as e:
            print(f"Error fetching VehicleId {vid}: {e}")
            full_info = {}

        ratings.append({
            "VehicleDescription": desc,
            "VehicleId": vid,
            "OverallRating": full_info.get("OverallRating"),
            "OverallFrontCrashRating": full_info.get("OverallFrontCrashRating"),
            "OverallSideCrashRating": full_info.get("OverallSideCrashRating"),
            "RolloverRating": full_info.get("RolloverRating"),
            "SidePoleCrashRating": full_info.get("SidePoleCrashRating"),
            "SideBarrierRatingOverall": full_info.get("SideBarrierRatingOverall"),
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


if __name__ == "__main__":
    print("🔧 Testing fetch_nhtsa_cars tool manually")
    try:
        year_input = input("Enter model year (default 2021): ").strip()
        make_input = input("Enter make (default Toyota): ").strip()
        model_input = input("Enter model (default Prius): ").strip()
        year = int(year_input) if year_input else 2018
        make = make_input or "Toyota"
        model = model_input or "Camry"

    except ValueError:
        print("Invalid year entered; using default 2021.")
        year, make = 2021, "Toyota"

    print(f"\nFetching NHTSA data for {make} {year}...")
    result = handle("local-test", {"year": year, "make": make, "model":model})
    print("\n=== Result ===")
    print(json.dumps(result, indent=2))
