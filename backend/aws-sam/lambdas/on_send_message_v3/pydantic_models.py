"""This is where the higest level of the payloads, (return and transmit) are defined"""

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel
from pydantic_input_comps import (SystemPrompt, InferenceConfig, 
                                  TextContentBlock, ToolConfig, ToolResultContentBlock)
from pydantic_resp_comps import Usage, ToolUse, ToolUseContentBlock

### Shared objects in both responses and inputs
ContentBlock = Union[TextContentBlock, ToolUseContentBlock, ToolResultContentBlock]


#TODO Don't allow raw dicts lmao

class Message(BaseModel):
    """A single User or Assistant message."""
    role: Literal["user", "assistant"]
    content: List[ContentBlock]

class Output(BaseModel):
    """The 'output' part of the response, containing the message."""
    message: Message

################### OVERARCHING INPUT PAYLOAD ############################

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


################### OVERARCHING RESULTANT PAYLOAD ############################


class ConverseResponse(BaseModel):
    """The main response object from the Converse API."""
    output: Output
    stopReason: Literal["end_turn", "tool_use", "max_tokens", "stop_sequence"]
    usage: Usage

    @property
    def message(self) -> Message:
        """Helper property to get the assistant's message directly."""
        return self.output.message

    def get_text_blocks(self) -> List[TextContentBlock]:
        """Extracts all text blocks from the response message."""
        texts = None
        for block in self.output.message.content:
            if isinstance(block, TextContentBlock):
                texts.append(block)
        return texts
    def get_text(self) -> str:
        """Extracts text from the response message."""
        for block in self.output.message.content:
            if isinstance(block, TextContentBlock):
                return block.text

    def get_tool_uses(self) -> List[ToolUse]:
        """Extracts all tool use requests from the response message."""
        tools = []
        for block in self.output.message.content:
            if isinstance(block, ToolUseContentBlock):
                tools.append(block.toolUse)
        return tools