'''Caller of Bedrock converse loop'''
import os
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
import boto3
import botocore

from db_tools_v2 import (build_history_messages, save_assistant_message, save_user_tool_results)

from pydantic_models import (ConversePayload, FullToolSpec, Message,
                             ToolConfig, ToolResultContentBlock, ToolSpecsOutput, ToolUse)
from converse_response_pydantic import ConverseResponse
from tools import tool_specs, tool_specs_output, dispatch
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

def call_orchestrator(connection_id: str, apigw, local = False) -> None:
    """Entry point called from Lambda — orchestrates one round using only transcript memory."""
    emitter = Emitter(apigw, connection_id,local)
    emitter.debug_emit("Starting call_orchestrator", {"connection_id": connection_id})
    history: List[Message] = build_history_messages(connection_id)
    ### this begins upon message sent from frontend
    for turn in range(MAX_TURNS):
        history = prune_history(history) ## This may be something we want to do in like the db_helpers
        tool_result_blocks: List[ToolResultContentBlock] = []

        emitter.debug_emit(f"Turn {turn} - History", history)

        tool_specs_list:  List[FullToolSpec] = tool_specs()
        system_prompt = build_system_prompt(tool_specs_list, turn, MAX_TURNS) ## turn aware prompt builder
        
        tool_info_blocks: ToolSpecsOutput = tool_specs_output()
        tool_config: ToolConfig = tool_info_blocks.tool_config
        payload = ConversePayload(modelId="ai21.jamba-1-5-large-v1:0",
                                  system=[system_prompt],
                                  messages=history,
                                  inferenceConfig={"temperature": 0.5},
                                  toolConfig=tool_config)
        try:
            resp = bedrock.converse(**payload.to_api_dict())
            response = ConverseResponse.model_validate(resp)
        except Exception as e: #pylint: disable=broad-exception-caught
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
        
        #### REFACTOR FROM HERE TO BELOW MARKER INTO METHOD
        if tool_uses:
            emitter.debug_emit("Tool Calls Detected", len(tool_uses))
            with ThreadPoolExecutor(max_workers=10) as executor:
                # Submit all tool calls in parallel
                futures = [
                    executor.submit(
                        dispatch,
                        tu.name,
                        connection_id,
                        tu.input,
                        tu.toolUseId,
                        bedrock
                    )
                    for tu in tool_uses
                ]

                # Emit progress as they start
                for tu in tool_uses:
                    emitter.emit(f"Calling tool: {tu.name}")

                # Collect results as they complete
                tool_result_blocks = []
                for future in as_completed(futures, timeout=30):  # 30 sec max per tool
                    try:
                        result = future.result()
                        tool_result_blocks.append(result)
                    except Exception as e:
                        # Optional: emit error per tool
                        emitter.emit(f"Tool failed: {e}")
                        # Or re-raise if you want to fail fast
                        raise
        emitter.debug_emit("All tool results ready", len(tool_result_blocks))
        ###################### THIS WILL RETURN TOOL USE BLOCKS
        
        if tool_result_blocks:
            user_tool_result_entry = Message(role="user", content=tool_result_blocks)
            save_user_tool_results(connection_id, tool_result_blocks)
            history.append(user_tool_result_entry)
            emitter.debug_emit("Tool Results Ready. Re-calling model.",user_tool_result_entry)