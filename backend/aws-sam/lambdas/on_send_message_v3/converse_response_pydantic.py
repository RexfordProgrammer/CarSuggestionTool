"""This is the pydantic response"""
from typing import List, Literal
from pydantic import BaseModel
from pydantic_models import Message,Output,Usage,TextContentBlock,ToolUse,ToolUseContentBlock


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
