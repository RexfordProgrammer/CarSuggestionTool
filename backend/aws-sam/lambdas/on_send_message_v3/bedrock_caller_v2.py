'''Caller of Bedrock converse loop'''
import os
from typing import List
import boto3
import botocore

from db_tools_v2 import (build_history_messages, save_assistant_message, save_user_tool_results)

from pydantic_models import (ConversePayload, FullToolSpec, Message, 
                            TextContentBlock, ToolConfig,
                            ToolResult, ToolResultContentBlock, ToolSpecsOutput, ToolUse)

from converse_pydantic import ConverseResponse
from tools import dispatch,tool_specs, tool_specs_output
from emitter import Emitter
from system_prompt_builder import build_system_prompt

bedrock = boto3.client(
    "bedrock-runtime",
    region_name=os.getenv("AWS_REGION", "us-east-1"),
    config=botocore.config.Config(connect_timeout=5, read_timeout=15),
)

DEBUG = True
MAX_TURNS = int(os.getenv("MAX_TURNS", "6"))
HISTORY_WINDOW = max(1, int(os.getenv("HISTORY_WINDOW", "10")))

def call_orchestrator(connection_id: str, apigw) -> None:
    """Entry point called from Lambda — orchestrates one round using only transcript memory."""
    emitter = Emitter(apigw, connection_id,DEBUG)

    emitter.debug_emit("Starting call_orchestrator", {"connection_id": connection_id})

    history: List[Message] = build_history_messages(connection_id)

    ### this begins upon message sent from frontend
    for turn in range(MAX_TURNS):
        tool_result_blocks: ToolResultContentBlock = []

        emitter.debug_emit("History: ", history)

        tool_specs_list:  List[FullToolSpec] = tool_specs()
        system_prompt = build_system_prompt(tool_specs_list)
        tool_info_blocks: ToolSpecsOutput = tool_specs_output()
        tool_config: ToolConfig = tool_info_blocks.tool_config
        # payload = build_payload(history)
        payload = ConversePayload(modelId="ai21.jamba-1-5-large-v1:0",
                                  system=[system_prompt],
                                  messages=history,
                                  interferenceConfig={"temperature": 0.5},
                                  toolConfig=tool_config)
            
        try:
            resp = bedrock.converse(**payload.to_api_dict())
            response = ConverseResponse.model_validate(resp)
        except Exception as e:
            err = f"Model call failed: {e}"
            emitter.emit(err)
            break
        
        save_assistant_message(connection_id, response) # persists and returns message
        assistant_text = response.get_text()
        history.append(response.output.message)
        tool_uses: List[ToolUse] = response.get_tool_uses()

        if not tool_uses: # If no tools, it's either the final answer or a nudge
            reply = "".join(assistant_text).strip() 
            if reply or turn == MAX_TURNS - 1: # If we have a reply, or we've hit max turns, emit and break
                if reply:
                    emitter.emit(reply)
                break
        
        emitter.debug_emit("Tool Calls Detected: ", len(tool_uses))

        for tu in tool_uses:
            emitter.emit(f"Calling tool:{tu.name} input {tu.input}")
            try:
                # MODIFIED: Dispatch now returns the final Pydantic content blocks.
                # The type should be List[Union[JsonContent, TextContentBlock]]
                validated_content = dispatch(tu.name, connection_id, tu.input)
                
                # Ensure it's a list of blocks before proceeding
                if not isinstance(validated_content, list):
                    raise TypeError("Tool handler did not return a list of Pydantic content blocks.")

            except Exception as e:
                err_payload = {"error": str(e)}
                emitter.emit(f"Tool {tu.name} failed: {str(err_payload)}")
                # Create a TextContentBlock to send the error back to the model
                error_content = [TextContentBlock(text=f"Tool execution failed: {str(e)}")]
                
                # Append a standardized error block to tool_result_blocks
                tr = ToolResult(toolUseId=tu.toolUseId, content=error_content)
                tr_contblock: ToolResultContentBlock = ToolResultContentBlock(toolResult=tr)
                tool_result_blocks.append(tr_contblock)
                # Skip to next tool use or re-call model
                continue
            tr = ToolResult(toolUseId=tu.toolUseId, content=validated_content)
            tr_contblock: ToolResultContentBlock = ToolResultContentBlock(toolResult=tr)

            tool_result_blocks.append(tr_contblock)
        if tool_result_blocks:
            user_tool_result_entry = Message(role="user", content=tool_result_blocks)
            save_user_tool_results(connection_id, tool_result_blocks)
            history.append(user_tool_result_entry)
            emitter.debug_emit("Tool Results Ready. Re-calling model.",user_tool_result_entry)
