"""Car Price Fetcher With Google API"""

from typing import Dict, Any, List, Union
import re
import requests

import json
import boto3
from botocore.exceptions import ClientError

from pydantic_input_comps import (ToolResult,JsonContent,
    ToolInputSchema,ToolSpec,FullToolSpec)
from pydantic_models import (
    ToolResultContentBlock,TextContentBlock)


def _get_secret(secret_name: str, region_name: str = "us-east-1") -> str | None:
    """
    Retrieve a secret value from AWS Secrets Manager.
    Returns the secret string (or JSON field if it's a dict).
    Falls back to os.getenv() for local runs.
    """
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=region_name)

    try:
        response = client.get_secret_value(SecretId=secret_name)
        secret = response["SecretString"]

        if secret.strip().startswith("{"):
            parsed = json.loads(secret)
            # Support both top-level key or generic secret
            return parsed.get(secret_name) or parsed.get(secret_name.lower())
        return secret

    except ClientError as e:
        # Common errors: secret doesn't exist, access denied, etc.
        error_code = e.response["Error"]["Code"]
        if error_code in ["ResourceNotFoundException", "AccessDeniedException"]:
            print(f"[SecretsManager] Warning: {secret_name} not found or access denied.")
        else:
            print(f"[SecretsManager] Error: {e}")
        return None
    except Exception as e: #pylint: disable=broad-exception-caught
        print(f"[SecretsManager] Unexpected error: {e}")
        return None

GOOGLE_API_KEY = _get_secret("GOOGLE_API_KEY")
GOOGLE_CX      = _get_secret("GOOGLE_CX")

if not GOOGLE_API_KEY or not GOOGLE_CX:
    raise EnvironmentError(
        "Missing GOOGLE_API_KEY or GOOGLE_CX. "
        "Set in AWS Secrets Manager or .env file."
    )




def prompt():
    """Tool-specific summarisation prompt – returns ONE estimated price."""
    p = (
        "You are given JSON with a list of price strings (price_strings) and source titles/links. "
        "Follow these steps exactly and output **only** the final sentence:\n"
        "1. Collect every dollar amount from `price_strings` and from any price mentioned in `sources.title` or `sources.link`.\n"
        "2. Remove any price < $500 or > $40,000 (junk or new-car MSRP).\n"
        "3. From the remaining numbers take the **median** (middle value when sorted).\n"
        "5. Output **exactly one sentence** in this format, nothing else:\n"
        "   'A <year> <make> <model> is worth $<rounded_median> in average condition.'\n"
        "Do NOT include ranges, explanations, JSON, or any other text."
    )
    return p

# ────────────────────────────────────────────────────────────────────────────────
# TOOL SPEC
# ────────────────────────────────────────────────────────────────────────────────
SPEC = FullToolSpec(
    toolSpec=ToolSpec(
        name="google_vehicle_price_lookup",
        description=(
            "Look up retail / trade-in price estimates for a vehicle using "
            "Google Custom Search (NADA, Edmunds, KBB). Returns low/high USD "
            "range extracted from search snippets."
        ),
        inputSchema=ToolInputSchema(
            json={
                "type": "object",
                "properties": {
                    "year": {"type": "integer", "description": "Model year"},
                    "make": {"type": "string", "description": "Vehicle make (default: Toyota)"},
                    "model": {"type": "string", "description": "Vehicle model"},
                },
                "required": ["year"],
                "additionalProperties": False,
            }
        ),
    )
).model_dump(by_alias=True)


# ────────────────────────────────────────────────────────────────────────────────
# Helper – single Google search + price extraction
# ────────────────────────────────────────────────────────────────────────────────
def _google_price_search(
    year: int, make: str, model: str | None
) -> Union[Dict[str, Any], Dict[str, str]]:
    """
    Returns either a dict with pricing data or an error dict.
    """
    if GOOGLE_API_KEY.startswith("YOUR_") or GOOGLE_CX.startswith("YOUR_"):
        return {"error": "Google API key / CX not set (use env vars)."}

    # Build the exact query we want Google to run
    base = f"{year} {make}"
    if model:
        base += f" {model}"
    q = f"{base} retail price OR trade-in site:nada.com OR site:edmunds.com OR site:kbb.com"

    url = (
        f"https://www.googleapis.com/customsearch/v1?"
        f"key={GOOGLE_API_KEY}&cx={GOOGLE_CX}&q={requests.utils.quote(q)}&num=10"
    )

    try:
        r = requests.get(url, timeout=12)
        if r.status_code == 403:
            return {"error": "Quota exceeded or invalid API key (100 free / day)."}
        if r.status_code == 429:
            return {"error": "Rate-limit hit (100 q / 100 s)."}
        r.raise_for_status()
        data = r.json()

        # ---- extract price strings from snippets ----
        price_strings: List[str] = []
        sources: List[Dict[str, str]] = []
        for item in data.get("items", []):
            snippet = item.get("snippet", "")
            sources.append({"title": item.get("title", ""), "link": item.get("link", "")})
            price_strings.extend(re.findall(r'\$[\d,]+(?:\s*-\s*\$[\d,]+)?', snippet))

        if not price_strings:
            return {
                "query_used": q,
                "message": "No price data in top results.",
                "sources": sources[:5],
            }

        # ---- parse to numbers, low / high ----
        def _to_int(p: str) -> List[int]:
            nums = []
            for part in p.replace(" - ", "-").split("-"):
                clean = re.sub(r"[^\d]", "", part.strip())
                if clean:
                    nums.append(int(clean))
            return nums

        all_nums = [n for s in price_strings for n in _to_int(s)]
        low = min(all_nums)
        high = max(all_nums)

        # plain-text summary (your style)
        summary = (
            f"{make} {model or ''} {year} price range: ${low:,} – ${high:,} USD "
            f"(sources: {', '.join([s['title'][:50] for s in sources[:3]])})"
        )

        return {
            "query_used": q,
            "low_estimate_usd": low,
            "high_estimate_usd": high,
            "summary": summary,
            "price_strings": price_strings[:10],
            "sources": sources[:5],
        }

    except Exception as exc: #pylint: disable=broad-exception-caught
        return {"error": str(exc)}


# ────────────────────────────────────────────────────────────────────────────────
# TOOL ENTRYPOINT
# ────────────────────────────────────────────────────────────────────────────────
def handle(connection_id: str, tool_input: Dict[str, Any], tool_use_id: str) -> ToolResultContentBlock:
    year = tool_input.get("year")
    make = tool_input.get("make", "Toyota")
    model = tool_input.get("model")

    # ---- basic validation ----
    if not year:
        return ToolResultContentBlock(
            toolResult=ToolResult(
                toolUseId=tool_use_id,
                content=[TextContentBlock(text="Error: 'year' is required.")],
            )
        )
    try:
        year_int = int(year)
    except ValueError:
        return ToolResultContentBlock(
            toolResult=ToolResult(
                toolUseId=tool_use_id,
                content=[TextContentBlock(text="Error: 'year' must be an integer.")],
            )
        )

    # ---- perform search ----
    cont = _google_price_search(year_int, make, model)

    if "error" in cont:
        return ToolResultContentBlock(
            toolResult=ToolResult(
                toolUseId=tool_use_id,
                content=[TextContentBlock(text=f"Search failed: {cont['error']}")],
            )
        )

    # ---- success payload ----
    payload = {
        "year": year_int,
        "make": make,
        "model": model,
        "pricing": cont,
        # "quota_info": "Free tier: 100 queries / day. Paid: $5 per 1000 beyond free.",
    }

    return ToolResultContentBlock(
        toolResult=ToolResult(
            toolUseId=tool_use_id,
            content=[JsonContent(json=payload)],
        )
    )


# if __name__ == "__main__":
#     import json

#     print("🔍 Testing google_vehicle_price_lookup tool...\n")

#     # Example test input
#     test_input = {
#         "year": 2020,
#         "make": "Toyota",
#         "model": "Camry",
#     }

#     print("Input:", test_input, "\n")

#     # Directly call the internal search helper
#     result = _google_price_search(
#         test_input["year"],
#         test_input["make"],
#         test_input["model"],
#     )

#     print("\nRaw result:")
#     print(json.dumps(result, indent=2))

#     # Also test the full tool handler with fake metadata
#     block = handle(
#         connection_id="local-test-connection",
#         tool_input=test_input,
#         tool_use_id="test_tool_use_id",
#     )

#     print("\nToolResultContentBlock:")
#     # block.model_dump() only works if your class inherits BaseModel
#     try:
#         print(json.dumps(block.model_dump(), indent=2, default=str))
#     except Exception:
#         print(block)
