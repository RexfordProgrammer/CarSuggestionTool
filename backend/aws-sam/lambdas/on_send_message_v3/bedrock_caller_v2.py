'''Caller of Bedrock converse loop'''
import os
from typing import List, Dict, Any
import boto3
import botocore

from converse_message_builder import (build_payload, create_tool_result_content_block,
                                      create_user_text_message,create_message)
from db_tools_v2 import (save_user_tool_result_entry_v2, save_assistant_from_bedrock_resp_v2,
                         build_history_messages,save_user_continue)
from bedrock_converse_handlers import extract_text_blocks, extract_tool_uses

from tools import dispatch
from emitter import Emitter

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

    history: List[Dict[str, Any]] = build_history_messages(connection_id)

    ### this begins upon message sent from frontend
    for turn in range(MAX_TURNS):
        tool_result_blocks: List[Dict[str, Any]] = []

        emitter.debug_emit("Turn: ", turn)
        emitter.debug_emit("History Size: ", len(history))
        emitter.debug_emit("History: ", history)

        payload = build_payload(history)

        try:
            resp = bedrock.converse(**payload)
        except Exception as e:
            err = f"Model call failed: {e}"
            emitter.emit(err)
            break

        assistant_entry = save_assistant_from_bedrock_resp_v2(connection_id, resp) # persists and returns message
        
        content = assistant_entry.get("content") or []
        history.append(assistant_entry) 

        tool_uses = extract_tool_uses(content)
        assistant_texts = extract_text_blocks(content)

        if not tool_uses: # If no tools, it's either the final answer or a nudge
            reply = "".join(assistant_texts).strip() 
            if reply or turn == MAX_TURNS - 1: # If we have a reply, or we've hit max turns, emit and break
                if reply:
                    emitter.emit(reply)
                break
            else:
                continue_message = create_user_text_message("continue")
                save_user_continue(connection_id)
                history.append(continue_message)
                continue
        
        emitter.debug_emit("Tool Calls Detected: ", len(tool_uses))

        # TOOL PROCESSING: This section executes the tool calls
        for tu in tool_uses:
            name = tu.get("name")
            tool_input = tu.get("input") or {}
            tool_use_id = tu.get("toolUseId")
            
            # Use emitter to show the tool call is happening
            emitter.emit(f"Calling tool:{name} input {tool_input}")

            try:
                # Dispatch tool call
                result = dispatch(name, connection_id, tool_input)
                # Use the new preview helper
                # preview_text = preview_tool_result(result)
            except Exception as e:
                err_payload = {"error": str(e)}
                # preview_text = preview_tool_result(err_payload)
                emitter.emit(f"Tool {name} failed: {str(e)}")
            
            ##### create tool block and append it to local toolused blocks
            tool_block = create_tool_result_content_block(tool_use_id, result)            
            tool_result_blocks.append(tool_block)

        if tool_result_blocks:
            
            user_tool_result_entry = create_message("user",tool_result_blocks)
            save_user_tool_result_entry_v2(connection_id, tool_result_blocks)
            history.append(user_tool_result_entry)
            emitter.debug_emit("Tool Results Ready. Re-calling model.",user_tool_result_entry)
            continue