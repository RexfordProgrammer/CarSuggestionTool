import requests
import json
from typing import Dict, List, Any

SPEC = {
    "toolSpec": {
        "name": "fetch_all_makes",
        "description": (
            "Retrieve a list of all vehicle manufacturers (makes) from the NHTSA database. "
            "This tool does not require any input. Use it when you need to validate or display "
            "the available makes before calling other tools like `fetch_cars_of_year`."
        ),
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            }
        },
    }
}


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


def handle(connection_id: str, tool_input: Dict) -> List[Dict]:
    """Handler function for Bedrock tool orchestration."""
    makes = _fetch_all_makes()
    return [
        {
            "json": {
                "count": len(makes),
                "makes": makes[:200],  # Limit for readability
            }
        }
    ]
