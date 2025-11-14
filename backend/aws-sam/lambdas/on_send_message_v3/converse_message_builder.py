
# ==========================
# JSON SAFE HELPERS
# ==========================
def json_safe(x):
    if isinstance(x, Decimal):
        return float(x)
    if isinstance(x, dict):
        return {k: json_safe(v) for k, v in x.items()}
    if isinstance(x, list):
        return [json_safe(v) for v in x]
    return x


def to_native_json(obj):
    if isinstance(obj, Decimal):
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    if isinstance(obj, dict):
        return {k: to_native_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_native_json(v) for v in obj]
    if isinstance(obj, (bytes, bytearray)):
        return obj.decode("utf-8", errors="replace")
    return obj
# Bedrock Converse Response Schema
# {
#   "outputText": "string or null",
#   "conversation": {
#     "messages": [
#       {
#         "id": "string",
#         "role": "assistant" | "user",
#         "content": [
#           {
#             "text": "string"
#           },
#           {
#             "type": "toolUse",
#             "id": "string",
#             "name": "string",
#             "input": { }
#           },
#           {
#             "type": "toolResult",
#             "toolUseId": "string",
#             "content": { }
#           }
#         ]
#       }
#     ]
#   },
#   "stopReason": "end_turn" | "tool_use" | "max_tokens" | "stop_sequence",
#   "metrics": {
#     "inputTokens": number,
#     "outputTokens": number
#   }
# }





# Messsage input payload shema
# {
#   "modelId": "ai21.jamba-1-5-large-v1:0",
#   "messages": [ ... ],
#   "inferenceConfig": {
#     "maxTokens": number,
#     "temperature": number,
#     "topP": number,
#     "stopSequences": ["string"]
#   },
#   "system": [
#     {
#       "text": "string"
#     }
#   ],
#   "tools": [
#     {
#       "toolSpec": {
#         "name": "fetch_cars_of_year",
#         "description": "string",
#         "inputSchema": {
#           "json": { ... JSON schema ... }
#         }
#       }
#     }
#   ],
#   "toolConfig": {
#     "tools": [
#       {
#         "toolSpec": {
#           "name": "fetch_cars_of_year",
#           "inputSchema": {
#             "json": { ... }
#           }
#         }
#       }
#     ]
#   }
# }


# User messages must be followed by assistant messages

# ToolUse Responses, 1 or more blocks are stored all as content blocks in a user message after toolcalls

# Messages Schema Input
# {
#   "messages": [
#     {
#       "role": "user" | "assistant",
#       "content": [                       List of Dicts
#         {
#           "type": "toolResult",
#           "toolUseId": "string",         Dict
#           "content": { }
#         },
#         {
#           "type": "toolResult",
#           "toolUseId": "string",         Dict
#           "content": { }
#         }
#       ]
#     }
#   ]
# }

### Create Content Blocks
from decimal import Decimal
from typing import Any, Dict, List
from tools import tool_specs
from system_prompt_builder import build_system_prompt


def create_text_content_block(text):
    content_block = {
        "text":text
    }
    return content_block


# {
#   "role": "user",
#   "content": [
#     {
#       "toolResult": {
#         "toolUseId": "a1b2c3d4-tool-use-id-5678",
#         "content": [
#           {
#             "json": {
#               "city": "Boston",
#               "temperature": 52,
#               "forecast": "Partly cloudy"
#             }
#           }
#         ]
#       }
#     }
#   ]
# }


# {
#   "toolResult": { 
#     "toolUseId": "tooluse_7mffsy20Scm4_dxc_rt7BA", 
#     "content": [ 
#       { "json": { ... } } 
#     ]
#   } 
# }
def create_tool_result_content_block(tool_use_id: str, tool_response_blocks: List[Dict]) -> Dict:
    if not tool_response_blocks or "json" not in tool_response_blocks[0]:
        raw_tool_data = {}
    else:
        raw_tool_data = tool_response_blocks[0]["json"] 
    tool_content_block = { 
        "json": raw_tool_data
    }
    tool_result_block = {
        "toolResult":{
            "toolUseId": tool_use_id,
            "content": [tool_content_block]
        }
    }
    return tool_result_block


def build_tool_info_blocks(tools):
    tool_blocks = {"tools": tools}
    return tool_blocks

def build_system_blocks(specs):
    system_prompt = build_system_prompt(specs)
    system_blocks = [{"text": system_prompt}]
    
    return system_blocks


# Messages Schema Input
# {
#   "messages": [
#     {
#       "role": ""user" | "assistant",
#       "content": [
#         {
#           "text": "string"
#         },
#         {
#           "type": "toolUse",
#           "id": "string",
#           "name": "string",
#           "input": { }
#         }
#       ]
#     }
#   ]
# }




### Genertic message creator
def create_message(role, content_blocks: List[Dict]) -> Dict:
    '''role can be user/assistant, content block type'''
    message = {
        "role": role, #user/assistant
        "content":content_blocks
    }
    return message

#### specific mesage creation
def create_user_text_message(text):
    text_cont_block = create_text_content_block(text) ## this returns the dict of a text content 
    message = create_message("user",[text_cont_block]) ## pass this single dict as a list of dicts with one element
    return message

def create_tool_response_message(tool_res_cont_blocks: List[Dict]):
    # tool_res_cont_block = create_tool_result_content_block(tool_use_id, tool_response_content)
    tool_response_message=create_message("user",tool_res_cont_blocks)
    return tool_response_message


# PAYLOADSPECS
# 
# {
#   "modelId": "string",                // REQUIRED
#   "messages": [ ... ],                // REQUIRED

#   "system": [                         // OPTIONAL
#     {
#       "text": "string"
#     }
#   ],

#   "inferenceConfig": {                // OPTIONAL
#     "maxTokens": number,
#     "temperature": number,
#     "topP": number,
#     "stopSequences": ["string"]
#   },

#   "toolConfig": {                     // OPTIONAL
#     "tools": [
#       {
#         "toolSpec": {
#           "name": "string",
#           "description": "string",
#           "inputSchema": {
#             "json": { ... }          // JSON Schema
#           }
#         }
#       }
#     ]
#   }
# }



def build_payload(history):
    tool_info = tool_specs()
    system_blocks = build_system_blocks(tool_info["specs"])
    tool_blocks = build_tool_info_blocks(tool_info["tool_config"]["tools"])
    
    payload = {
            "modelId": "ai21.jamba-1-5-large-v1:0",
            "system": system_blocks,
            "messages": history,
            "toolConfig": tool_blocks,
            "inferenceConfig": {"temperature": 0.5},
        }
    
    return to_native_json(payload)


# Response Body from Bedrock Converse
# {
#   "output": {
#     "message": {
#       "role": "assistant",
#       "content": [
#         // This array will contain one or more parts:
#         {
#           // 1. TEXT PART (If the assistant generates text)
#           "text": "The weather in Boston is currently 52 degrees and partly cloudy."
#         },
#         {
#           // 2. TOOL USE PART (If the assistant wants to call a tool)
#           "toolUse": {
#             "toolUseId": "tool_call_001",
#             "name": "get_current_weather",
#             "input": {
#               "city": "Boston"
#             }
#           }
#         }
#       ]
#     }
#   },
#   "stopReason": "end_of_turn", // or "tool_use"
#   "usage": {
#     "inputTokens": 200,
#     "outputTokens": 50
#   }
# }


def extract_message_from_response(resp):
    message_body = resp.get("output", {}).get("message", {})
    return message_body

# ==========================
# EXTRACTION UTILITIES
# ==========================
def extract_text_blocks(content: List[Dict[str, Any]]) -> List[str]:
    out = []
    for c in content or []:
        if isinstance(c, dict) and "text" in c:
            out.append(str(c["text"]))
    return out


def extract_tool_uses(content: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    uses = []
    for c in content or []:
        if isinstance(c, dict) and isinstance(c.get("toolUse"), dict):
            uses.append(c["toolUse"])
    return uses
