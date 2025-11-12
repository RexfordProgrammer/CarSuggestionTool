
# {
#   "output": {
#     "message": {
#       "role": "assistant",
#       "content": [
#         {
#           "toolUse": {
#             "toolUseId": "tooluse_4Jk0OVe_TO6eDJKSoqLcrA",
#             "name": "fetch_vehicles_by_year",
#             "input": {
#               "year": 2020
#             }
#           }
#         },
#         {
#           "text": "Let me look up 2020 vehicles for you."
#         }
#       ]
#     }
#   }
# }


from typing import Any, Dict, List, Optional

def get_bedrock_message(resp: Dict[str, Any]) -> Dict[str, Any]:
    """
    Given a full bedrock.converse response, return the inner `message` dict.
    Safe against missing keys.
    """
    if not isinstance(resp, dict):
        return {}
    output = resp.get("output") or {}
    message = output.get("message") or {}
    # message should look like: {"role": "assistant", "content": [ ... ]}
    return message


def get_content_blocks(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Get the `content` blocks from either:
      - a full bedrock response (with `output.message`)
      - or a bare message dict (with `content`)

    Always returns a list of dicts.
    """
    # If it's a full response, drill down to message first
    if "output" in obj:
        message = get_bedrock_message(obj)
        content = message.get("content") or []
    else:
        content = obj.get("content") or []

    if isinstance(content, list):
        return content
    # Defensive: if the model somehow sent a single block, wrap it
    return [content]


# =====================================================
# Introspection helpers
# =====================================================

def get_tool_uses_from_content(content: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Return the raw `toolUse` dicts from a list of Bedrock content blocks.
    Each toolUse looks like:
      {
        "toolUseId": "...",
        "name": "...",
        "input": {...}
      }
    """
    tool_uses: List[Dict[str, Any]] = []
    for block in content or []:
        if not isinstance(block, dict):
            continue
        tu = block.get("toolUse")
        if isinstance(tu, dict):
            tool_uses.append(tu)
    return tool_uses


def get_tool_use_blocks_from_content(content: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Return the *blocks* that contain toolUse (not just the inner dict),
    e.g. [{ "toolUse": {...} }, ...]
    """
    blocks: List[Dict[str, Any]] = []
    for block in content or []:
        if isinstance(block, dict) and "toolUse" in block:
            blocks.append(block)
    return blocks


def get_text_blocks_from_content(content: List[Dict[str, Any]]) -> List[str]:
    """
    Collect all 'text' fields from the blocks as strings.
    """
    texts: List[str] = []
    for block in content or []:
        if not isinstance(block, dict):
            continue
        if "text" in block:
            texts.append(str(block["text"]))
    return texts


def get_first_tool_use(resp: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Convenience: given a full response, return the first toolUse dict (or None).
    """
    content = get_content_blocks(resp)
    uses = get_tool_uses_from_content(content)
    return uses[0] if uses else None


def get_all_text_from_resp(resp: Dict[str, Any], sep: str = " ") -> str:
    """
    Convenience: get all assistant text from a response, joined.
    """
    content = get_content_blocks(resp)
    texts = get_text_blocks_from_content(content)
    return sep.join(texts).strip()


# =====================================================
# Dynamo-friendly helpers
# =====================================================

def bedrock_message_to_dynamo(message: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a Bedrock `message` dict to your DynamoDB message shape:
        { "role": "assistant" | "user", "content": [ ...blocks... ] }

    Assumes the message already uses Bedrock-native content blocks.
    """
    role = message.get("role", "assistant")
    content = message.get("content") or []

    # Ensure list; Dynamo is fine with nested lists/maps
    if not isinstance(content, list):
        content = [content]

    return {
        "role": role,
        "content": content,
    }


def dynamo_entry_from_resp(resp: Dict[str, Any]) -> Dict[str, Any]:
    """
    One-shot: take a full bedrock.converse response and turn it into a
    Dynamo-friendly message entry that preserves native content blocks.
    """
    message = get_bedrock_message(resp)
    return bedrock_message_to_dynamo(message)
