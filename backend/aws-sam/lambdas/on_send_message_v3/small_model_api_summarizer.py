"""API CALL PARAPHRASER - Pydantic I/O"""
import json
from pydantic_input_comps import ToolResult
from pydantic_models import (SystemPrompt, Message, TextContentBlock,
                             InferenceConfig, ConversePayload, ConverseResponse, ToolResultContentBlock)

MODEL_ID = "ai21.jamba-1-5-mini-v1:0"

def create_summary_result_block(
    bdrk, 
    original_tool_result_block: ToolResultContentBlock,
    instruction_prompt = "Extract the essential meaning from this JSON data and rewrite it as a brief plain-English statement. Remove all JSON formatting, IDs, and internal structure noise."
) -> ToolResultContentBlock:
    """
    Takes an input ToolResultContentBlock, extracts the raw data, summarizes it 
    using an LLM, and returns a new ToolResultContentBlock containing the summary 
    as TextContentBlock.
    """
    
    tool_result_data = original_tool_result_block.toolResult.model_dump()
    tool_use_id = original_tool_result_block.toolResult.toolUseId
    
    try:
        raw_json_data = tool_result_data['content'][0]['json']
    except (KeyError, IndexError):
        raw_json_data = tool_result_data
    content_string = json.dumps(raw_json_data, indent=2)

    
    user_prompt_text = f"{instruction_prompt}\n\n--- DATA ---\n{content_string}"
    system_prompt_model = SystemPrompt(text="You are an expert at simplifying technical data into concise summaries.")
    user_content_block = TextContentBlock(text=user_prompt_text)
    user_message = Message(role="user", content=[user_content_block])
    inference_config = InferenceConfig(maxTokens=120, temperature=0.2)

    payload = ConversePayload(
        modelId=MODEL_ID,
        system=[system_prompt_model],
        messages=[user_message],
        inferenceConfig=inference_config
    )

    raw_rep = bdrk.converse(**payload.to_api_dict())

    converse_response = ConverseResponse(**raw_rep)

    summary_blocks = converse_response.output.message.content
    
    summary_text = [
        block.text for block in summary_blocks 
        if isinstance(block, TextContentBlock)
    ]
    
    final_summary_text = "TOOL RESULTS: \n".join(summary_text)

    summary_content_block = TextContentBlock(text=final_summary_text)
    
    summarized_tool_result = ToolResult(
        toolUseId=tool_use_id, # Must preserve the original ID
        content=[summary_content_block]
    )
    
    return ToolResultContentBlock(toolResult=summarized_tool_result)