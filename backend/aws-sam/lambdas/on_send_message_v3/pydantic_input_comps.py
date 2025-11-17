"""Pydantic model declarations for payloads to the model, including tool specs and """
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

#### System Prompt Input ####
class SystemPrompt(BaseModel):
    """A system prompt content block."""
    text: str

##############################
class ToolInputSchema(BaseModel):
    """Models the 'inputSchema' part of the tool specification."""
    # Using alias for schema compatibility with 'json' key
    json: Dict[str, Any] = Field(..., alias="json") 

class ToolSpec(BaseModel):
    """The core specification for a single tool."""
    name: str
    description: Optional[str] = None
    inputSchema: ToolInputSchema

class FullToolSpec(BaseModel):
    """Models the complete SPEC object required by the tool modules (t.SPEC)."""
    toolSpec: ToolSpec

class ToolConfigItem(BaseModel):
    """The Bedrock API requires each tool spec to be wrapped in a 'toolSpec' key."""
    toolSpec: ToolSpec

class ToolConfig(BaseModel):
    """It expects a list of ToolConfigItem objects."""
    tools: List[ToolConfigItem] 

class ToolSpecsBundle(BaseModel): #TODO Rename to tool specs container
    """Models the output structure of the tool_specs() function."""
    tool_config: ToolConfig
    specs: List[Dict[str, Any]]

############### INPUT TOOL !!!!!!!!!!!!! CONFIGURATIONS !!!!!!!!!!!! ##############

class JsonContent(BaseModel):
    """The JSON payload for a tool result."""
    json: Dict[str, Any]

class TextContentBlock(BaseModel):
    """A simple text block."""
    text: str

ToolResultContentType = Union[ JsonContent, TextContentBlock, Dict[str, Any] ]

class ToolResult(BaseModel):
    """The result of a tool execution."""
    toolUseId: str
    content: List[ToolResultContentType] 

class ToolResultContentBlock(BaseModel):
    """A block wrapper for a tool result."""
    toolResult: ToolResult

############### INPUT TOOL !!!!!!!!!!!!! RESULTS !!!!!!!!!!!! ##############

class InferenceConfig(BaseModel):
    """Configuration for inference."""
    maxTokens: Optional[int] = None
    temperature: Optional[float] = None
    topP: Optional[float] = None
    stopSequences: Optional[List[str]] = None

################### Inference settins for payload ############################