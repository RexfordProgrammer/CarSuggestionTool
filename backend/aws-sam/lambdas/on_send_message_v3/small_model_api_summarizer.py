"""API CALL PARAPHRASER"""
import os
import boto3
import botocore
import json
MODEL_ID = "ai21.jamba-1-5-mini-v1:0"
from pydantic_models import SystemPrompt

def summarize_api_call(bdrk, input) -> str:
    prompt_text = "Extract the essential meaning from this data and rewrite it as a brief plain-English statement. Remove all noise."
    
    system_prompt = SystemPrompt(text=prompt_text)

    rep = bdrk.converse(
    modelId="ai21.jamba-1-5-mini-v1:0",
    system=[
        {"text": system_prompt.text} 
    ],
    messages=[
        {
            "role": "user",
            "content": [
                {"text": input}
            ],
        }
    ],
    inferenceConfig={
        "maxTokens": 120,
        "temperature": 0.2,
    }
)

    
    # Extract assistant text
    blocks = rep["output"]["message"]["content"]
    return "\n".join([b["text"] for b in blocks])


if __name__ == "__main__":
    bedrock = boto3.client(
        "bedrock-runtime",
        region_name=os.getenv("AWS_REGION", "us-east-1"),
        config=botocore.config.Config(connect_timeout=5, read_timeout=15),
    )
    
    resp=summarize_api_call(bedrock, "JsonContent(json={'vehicle_id': '44074', 'make': 'Toyota', 'model': 'Corolla', 'year': 2022, 'fuel_type': 'Regular Gasoline', 'city_mpg': 31.0, 'highway_mpg': 40.0, 'combined_mpg': 34.0, 'co2_grams_per_mile': 257.0, 'fuel_cost_annual': 1350.0JsonContent(json={'year': 2022, 'make': 'Toyota', 'model': 'Corolla', 'count': 1, 'ratings': [{'VehicleDescription': '2022 Toyota COROLLA 4 DR FWD', 'VehicleId': 16634, 'OverallRating': '5', 'OverallFrontCrashRating': '5', 'OverallSideCrashRating': '5', 'RolloverRating': '4', 'SidePoleCrashRating': '5', 'SideBarrierRatingOverall': None}]})]))]")
    print (resp)
    
    