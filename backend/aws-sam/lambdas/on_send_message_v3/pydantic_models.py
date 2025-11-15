from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field

class ToolInputSchema(BaseModel):
    """Models the 'inputSchema' part of the tool specification."""
    json_data: Dict[str, Any] = Field(..., alias="json")  # ← renamed + alias preserved
    
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

class ToolSpecsOutput(BaseModel):
    """Models the output structure of the tool_specs() function."""
    tool_config: ToolConfig
    specs: List[Dict[str, Any]]

class TextContentBlock(BaseModel):
    """A simple text block."""
    text: str

class ToolUse(BaseModel):
    """The model's request to use a tool."""
    toolUseId: str
    name: str
    input: Dict[str, Any]

class ToolUseContentBlock(BaseModel):
    """A block wrapper for a tool use request."""
    toolUse: ToolUse
    
class JsonContent(BaseModel):
    """The JSON payload for a tool result."""
    json_data: Dict[str, Any] = Field(..., alias="json")  # ← renamed + alias preserved

# 1. Define the possible content types for a ToolResult
ToolResultContentType = Union[
    JsonContent,
    TextContentBlock,
    Dict[str, Any]  # allow raw dicts from dispatch()
]

class ToolResult(BaseModel):
    """The result of a tool execution."""
    toolUseId: str
    # FIX: Change from List[JsonContent] to accept the union of all content models
    content: List[ToolResultContentType] 
        # OR: content: List[Union[JsonContent, TextContentBlock]]
    
class ToolResultContentBlock(BaseModel):
    """A block wrapper for a tool result."""
    toolResult: ToolResult

ContentBlock = Union[TextContentBlock, ToolUseContentBlock, ToolResultContentBlock]

class Message(BaseModel):
    """A single User or Assistant message."""
    role: Literal["user", "assistant"]
    content: List[ContentBlock]

class SystemPrompt(BaseModel):
    """A system prompt content block."""
    text: str

# API PAYLOADS

class InferenceConfig(BaseModel):
    """Configuration for inference."""
    maxTokens: Optional[int] = None
    temperature: Optional[float] = None
    topP: Optional[float] = None
    stopSequences: Optional[List[str]] = None


class ConversePayload(BaseModel):
    """The main request payload for the Converse API."""
    modelId: str
    messages: List[Message]
    
    system: Optional[List[SystemPrompt]] = None
    inferenceConfig: Optional[InferenceConfig] = None
    toolConfig: Optional[ToolConfig] = None # Now accepts the same type as ToolConfig

    def to_api_json(self) -> str:
        """Serializes the payload for the API request."""
        return self.model_dump_json(exclude_none=True)
    
    def to_api_dict(self) -> Dict[str, Any]:
        """Serializes the payload for the API request."""
        return self.model_dump(exclude_none=True, mode='json')


# API RESPONSE

class Usage(BaseModel):
    """Token usage metrics."""
    inputTokens: int
    outputTokens: int

class Output(BaseModel):
    """The 'output' part of the response, containing the message."""
    message: Message

class ConverseResponse(BaseModel): 
    """The main response object from the Converse API."""
    output: Output
    stopReason: Literal["end_turn", "tool_use", "max_tokens", "stop_sequence"]
    usage: Usage