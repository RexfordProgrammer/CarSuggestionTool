# tools/fetch_nhtsa_cars.py
import requests
from typing import Dict, List, Any

SPEC = {
    "toolSpec": {
        "name": "fetch_nhtsa_cars",
        "description": (
            "Query the official NHTSA Vehicle API for all makes and models available "
            "in a given model year. Returns a structured JSON list of results."
        ),
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": "The model year to fetch vehicles for (e.g., 2021)."
                    }
                },
                "required": ["year"],
                "additionalProperties": False
            }
        }
    }
}


def _fetch_from_nhtsa(year: int) -> List[Dict[str, Any]]:
    """Call the NHTSA API for a given model year and return structured results."""
    base_url = f"https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForYear/{year}?format=json"

    try:
        resp = requests.get(base_url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"Error fetching data from NHTSA: {e}")
        return []

    results = data.get("Results", [])
    cars = [
        {
            "Make_ID": r.get("Make_ID"),
            "Make_Name": r.get("Make_Name"),
            "Model_ID": r.get("Model_ID"),
            "Model_Name": r.get("Model_Name"),
        }
        for r in results
        if r.get("Make_Name") and r.get("Model_Name")
    ]
    return cars


def handle(connection_id: str, tool_input: Dict) -> List[Dict]:
    """Main tool entry point for the orchestrator."""
    year = None
    if isinstance(tool_input, dict):
        year = tool_input.get("year")

    if not year:
        return [{"text": "Error: Missing 'year' in tool input."}]

    cars = _fetch_from_nhtsa(int(year))

    # Return formatted JSON for orchestration
    return [{"json": {"year": year, "count": len(cars), "vehicles": cars[:100]}}]
