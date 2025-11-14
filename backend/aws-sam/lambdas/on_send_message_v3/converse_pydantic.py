from typing import List, Literal
from pydantic import BaseModel
from tools import tool_specs
from pydantic_models import Message,Output, ToolConfig,Usage,TextContentBlock,ToolUse,ToolUseContentBlock


class ConverseResponse(BaseModel):
    """The main response object from the Converse API."""
    output: Output
    stopReason: Literal["end_turn", "tool_use", "max_tokens", "stop_sequence"]
    usage: Usage

    # This REPLACES extract_message_from_response()
    @property
    def message(self) -> Message:
        """Helper property to get the assistant's message directly."""
        return self.output.message

    # This REPLACES extract_text_blocks()
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

    # This REPLACES extract_tool_uses()
    def get_tool_uses(self) -> List[ToolUse]:
        """Extracts all tool use requests from the response message."""
        tools = []
        for block in self.output.message.content:
            if isinstance(block, ToolUseContentBlock):
                tools.append(block.toolUse)
        return tools
    

def get_tool_info_blocks() -> ToolConfig:
    """
    Retrieves the necessary tool configuration data by calling tool_specs()
    and extracts the Pydantic ToolConfig object.
    """
    tool_specs_output = tool_specs()
    tool_config_blocks = tool_specs_output.tool_config
    
    return tool_config_blocks