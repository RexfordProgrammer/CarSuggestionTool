# tools/fetch_fuel_economy.py
import requests
from typing import Dict, Any
import xml.etree.ElementTree as ET

from pydantic_models import (
    ToolResultContentBlock,
    ToolResult,
    TextContentBlock,
    JsonContent,
    ToolInputSchema,
    ToolSpec,
    FullToolSpec
)

# ────────────────────────────────────────────────────────────────────────────────
# TOOL SPEC (converted to Pydantic)
# ────────────────────────────────────────────────────────────────────────────────
SPEC = FullToolSpec(
    toolSpec=ToolSpec(
        name="fetch_gas_mileage",
        description="Get gas mileage and CO₂ data for a vehicle (model optional).",
        inputSchema=ToolInputSchema(
            json={
                "type": "object",
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": "Model year (e.g., 2022)"
                    },
                    "make": {
                        "type": "string",
                        "description": "Manufacturer (e.g., Toyota)"
                    },
                    "model": {
                        "type": "string",
                        "description": "Model name (e.g., Camry)"
                    }
                },
                "required": ["year", "make", "model"],
                "additionalProperties": False
            }
        )
    )
).model_dump(by_alias=True)


# ────────────────────────────────────────────────────────────────────────────────
# HELPERS
# ────────────────────────────────────────────────────────────────────────────────

def _get_vehicle_id(year: int, make: str, model: str) -> str:
    url = f"https://www.fueleconomy.gov/ws/rest/vehicle/menu/options?year={year}&make={make}&model={model}"

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()

        if "application/json" not in resp.headers.get("Content-Type", ""):
            root = ET.fromstring(resp.text)
            menu_items = root.findall(".//menuItem")
            if not menu_items:
                return None
            return menu_items[0].findtext("value")
        else:
            data = resp.json()
            options = data.get("menuItem", [])
            return options[0]["value"] if options else None

    except Exception as e:
        print(f"Error fetching vehicle ID: {e}")
        return None


def _fetch_vehicle_details(vehicle_id: str) -> Dict[str, Any]:
    url = f"https://www.fueleconomy.gov/ws/rest/vehicle/{vehicle_id}"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()

        if "application/json" not in resp.headers.get("Content-Type", ""):
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


# ────────────────────────────────────────────────────────────────────────────────
# TOOL ENTRYPOINT — **Always returns ToolResultContentBlock**
# ────────────────────────────────────────────────────────────────────────────────

def handle(connection_id: str, tool_input: Dict[str, Any], tool_use_id: str) -> ToolResultContentBlock:
    """
    Fetch fuel economy stats for a vehicle and ALWAYS return ToolResultContentBlock.
    """

    year = tool_input.get("year")
    make = tool_input.get("make")
    model = tool_input.get("model")

    # 1. Validate input
    if not (year and make and model):
        tb = TextContentBlock(text="Error: Missing required fields (year, make, model).")
        return ToolResultContentBlock(
            toolResult=ToolResult(toolUseId=tool_use_id, content=[tb])
        )

    # 2. Vehicle ID lookup
    vehicle_id = _get_vehicle_id(year, make, model)
    if not vehicle_id:
        tb = TextContentBlock(text=f"No vehicle found for {year} {make} {model}.")
        return ToolResultContentBlock(
            toolResult=ToolResult(toolUseId=tool_use_id, content=[tb])
        )

    # 3. Fetch details
    details = _fetch_vehicle_details(vehicle_id)

    # 4. Handle detail error
    if "error" in details:
        tb = TextContentBlock(
            text=f"Could not retrieve details for vehicle ID {vehicle_id}: {details['error']}"
        )
        return ToolResultContentBlock(
            toolResult=ToolResult(toolUseId=tool_use_id, content=[tb])
        )

    # 5. SUCCESS → JsonContent
    jc = JsonContent(json=details)
    return ToolResultContentBlock(
        toolResult=ToolResult(toolUseId=tool_use_id, content=[jc])
    )
