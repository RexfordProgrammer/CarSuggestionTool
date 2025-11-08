# tools/fetch_fuel_economy.py
import requests, json
from typing import Dict, List, Any

SPEC = {
    "toolSpec": {
        "name": "fetch_fuel_economy",
        "description": (
            "Retrieve EPA fuel economy and emissions data for a given vehicle "
            "specified by year, make, and model using the FuelEconomy.gov API."
        ),
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": "Model year of the vehicle (e.g., 2022)."
                    },
                    "make": {
                        "type": "string",
                        "description": "Manufacturer name (e.g., Toyota)."
                    },
                    "model": {
                        "type": "string",
                        "description": "Model name (e.g., Camry)."
                    }
                },
                "required": ["year", "make", "model"],
                "additionalProperties": False
            }
        }
    }
}


def _get_vehicle_id(year: int, make: str, model: str) -> str:
    """
    Step 1: Find the vehicle ID for the given year/make/model.
    This identifies the specific trim or engine configuration.
    """
    url = f"https://www.fueleconomy.gov/ws/rest/vehicle/menu/options?year={year}&make={make}&model={model}"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        # The API often returns XML, but newer responses can be JSON if header included.
        if "application/json" not in resp.headers.get("Content-Type", ""):
            import xml.etree.ElementTree as ET
            root = ET.fromstring(resp.text)
            menu_items = root.findall(".//menuItem")
            if not menu_items:
                return None
            # Grab first available vehicle ID
            return menu_items[0].findtext("value")
        else:
            data = resp.json()
            options = data.get("menuItem", [])
            return options[0]["value"] if options else None
    except Exception as e:
        print(f"Error fetching vehicle ID: {e}")
        return None


def _fetch_vehicle_details(vehicle_id: str) -> Dict[str, Any]:
    """
    Step 2: Retrieve full fuel economy and CO₂ data for that specific vehicle ID.
    """
    url = f"https://www.fueleconomy.gov/ws/rest/vehicle/{vehicle_id}"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()

        if "application/json" not in resp.headers.get("Content-Type", ""):
            # Parse XML to extract common fields
            import xml.etree.ElementTree as ET
            root = ET.fromstring(resp.text)
            get = lambda tag: root.findtext(tag)
            return {
                "vehicle_id": vehicle_id,
                "make": get("make"),
                "model": get("model"),
                "year": int(get("year") or 0),
                "fuel_type": get("fuelType1"),
                "city_mpg": float(get("city08") or 0),
                "highway_mpg": float(get("highway08") or 0),
                "combined_mpg": float(get("comb08") or 0),
                "co2_grams_per_mile": float(get("co2TailpipeGpm") or 0),
                "fuel_cost_annual": float(get("fuelCost08") or 0),
            }
        else:
            data = resp.json().get("vehicle", {})
            return {
                "vehicle_id": vehicle_id,
                "make": data.get("make"),
                "model": data.get("model"),
                "year": int(data.get("year", 0)),
                "fuel_type": data.get("fuelType1"),
                "city_mpg": float(data.get("city08", 0)),
                "highway_mpg": float(data.get("highway08", 0)),
                "combined_mpg": float(data.get("comb08", 0)),
                "co2_grams_per_mile": float(data.get("co2TailpipeGpm", 0)),
                "fuel_cost_annual": float(data.get("fuelCost08", 0)),
            }
    except Exception as e:
        print(f"Error fetching fuel economy details: {e}")
        return {"error": str(e)}


def handle(connection_id: str, tool_input: Dict) -> List[Dict]:
    """
    Main Bedrock-tool handler.
    """
    year = tool_input.get("year")
    make = tool_input.get("make")
    model = tool_input.get("model")

    if not (year and make and model):
        return [{"text": "Error: Missing required fields (year, make, model)."}]

    vehicle_id = _get_vehicle_id(year, make, model)
    if not vehicle_id:
        return [{"text": f"No vehicle found for {year} {make} {model}."}]

    details = _fetch_vehicle_details(vehicle_id)
    return [{"json": details}]
