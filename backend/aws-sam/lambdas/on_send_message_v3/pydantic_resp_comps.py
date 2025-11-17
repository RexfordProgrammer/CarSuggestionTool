"""This is the pydantic response"""
from typing import Any, Dict
from pydantic import BaseModel

class ToolUse(BaseModel):
    """The model's request to use a tool."""
    toolUseId: str
    name: str
    input: Dict[str, Any]

class ToolUseContentBlock(BaseModel):
    """A block wrapper for a tool use request."""
    toolUse: ToolUse

class Usage(BaseModel):
    """Token usage metrics."""
    inputTokens: int
    outputTokens: int
