
HISTORY_WINDOW_SOFT_CLIP = 20 # The number of recent messages to always keep

from typing import List
from pydantic_models import Message, ToolResultContentBlock,ToolUseContentBlock


def prune_history(history: List[Message]) -> List[Message]:
    """
    Prunes the conversation history to manage token count and focus on recent turns.
    """
    if not history:
        return []
    # 1. Hard Clip
    pruned_history = history[-HISTORY_WINDOW_SOFT_CLIP:]
    while pruned_history:
        current_message = pruned_history[0]
        if (current_message.role=="assistant"):
            pruned_history.pop(0)
        is_tool_result_content = any(
            isinstance(block, ToolResultContentBlock) or  isinstance(block, ToolUseContentBlock)
            for block in current_message.content
        )
        
        if is_tool_result_content and len(current_message.content) == len(pruned_history[0].content):
            pruned_history.pop(0)
        else:
            break

    return pruned_history