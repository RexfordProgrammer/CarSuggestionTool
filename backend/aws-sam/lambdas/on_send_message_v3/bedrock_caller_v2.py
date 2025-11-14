'''Caller of Bedrock converse loop'''
import os
from typing import List
import boto3
import botocore

from db_tools_v2 import (build_history_messages, save_assistant_message, save_user_tool_results)

from pydantic_models import (ConversePayload, FullToolSpec, Message, 
                            TextContentBlock, ToolConfig,
                            ToolResult, ToolResultContentBlock, ToolSpecsOutput, ToolUse)
from typing import List
from pydantic_models import Message, ToolResultContentBlock 
from converse_pydantic import ConverseResponse
from tools import dispatch,tool_specs, tool_specs_output
from emitter import Emitter
from system_prompt_builder import build_system_prompt
from prune_history import prune_history

bedrock = boto3.client(
    "bedrock-runtime",
    region_name=os.getenv("AWS_REGION", "us-east-1"),
    config=botocore.config.Config(connect_timeout=5, read_timeout=15),
)

DEBUG = True
MAX_TURNS = int(os.getenv("MAX_TURNS", "4"))

def call_orchestrator(connection_id: str, apigw) -> None:
    """Entry point called from Lambda — orchestrates one round using only transcript memory."""
    emitter = Emitter(apigw, connection_id,DEBUG)

    emitter.debug_emit("Starting call_orchestrator", {"connection_id": connection_id})

    history: List[Message] = build_history_messages(connection_id)
    
    ### this begins upon message sent from frontend
    for turn in range(MAX_TURNS):
        history = prune_history(history) ## This may be something we want to do in like the db_helpers
        tool_result_blocks: List[ToolResultContentBlock] = []

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
            tr_block:ToolResultContentBlock = dispatch(tu.name, connection_id, tu.input, tu.toolUseId)
            # if not isinstance(validated_content, list):
            #     raise TypeError("Tool handler did not return a list of Pydantic content blocks.")
            # tr = ToolResult(toolUseId=tu.toolUseId, content=validated_content)
            # tr_contblock: ToolResultContentBlock = ToolResultContentBlock(toolResult=tr)
            # #List[ToolResultContentBlock]
            tool_result_blocks.append(tr_block)

        if tool_result_blocks:
            user_tool_result_entry = Message(role="user", content=tool_result_blocks)
            save_user_tool_results(connection_id, tool_result_blocks)
            history.append(user_tool_result_entry)
            emitter.debug_emit("Tool Results Ready. Re-calling model.",user_tool_result_entry)