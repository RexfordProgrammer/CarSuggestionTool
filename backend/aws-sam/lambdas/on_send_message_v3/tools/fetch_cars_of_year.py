import requests
import json
from typing import Dict, List, Any

SPEC = {
    "toolSpec": {
        "name": "fetch_nhtsa_cars",
        "description": "Query NHTSA Vehicle API for models available in a given year (optionally by make).",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "year": {"type": "integer"},
                    "make": {"type": "string"},
                },
                "required": ["year"],
            }
        },
    }
}


def _fetch_from_nhtsa(year: int, make: str = "Toyota") -> List[Dict[str, Any]]:
    """Fetch models for a given make/year."""
    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMakeYear/make/{make}/modelyear/{year}?format=json"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("Results", [])
        return [
            {
                "Make_Name": r.get("Make_Name"),
                "Model_Name": r.get("Model_Name"),
                "Model_ID": r.get("Model_ID"),
            }
            for r in results
        ]
    except Exception as e:
        print(f"Error fetching data from NHTSA: {e}")
        return []


def handle(connection_id: str, tool_input: Dict) -> List[Dict]:
    year = int(tool_input.get("year"))
    make = tool_input.get("make", "Toyota")  # default make
    cars = _fetch_from_nhtsa(year, make)
    return [{"json": {"year": year, "make": make, "count": len(cars), "vehicles": cars[:100]}}]