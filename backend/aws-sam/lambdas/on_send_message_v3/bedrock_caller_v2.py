import os
from typing import List, Dict, Any
import boto3
import botocore
from system_prompt_builder import build_system_prompt

# Assuming 'tools' contains dispatch and tool_specs
from tools import dispatch, tool_specs

# Importing utilities from the provided handlers (bedrock_converse_handlers/db_tools)
from bedrock_converse_handlers import (
    extract_text_chunks,
    extract_tool_uses,
)

# Importing utilities from the second code block
from bedrock_converse_handlers import (
    preview_tool_result,
    to_native_json,
)

# Importing utilities from db_tools.py
from db_tools import (
    save_assistant_from_bedrock_resp,
    build_history_messages,
    append_message_entry, # For error handling
    save_user_continue,
    save_user_tool_result_entry
)

from emitter import Emitter

# ==========================
# CONFIGURATION
# ==========================
ORCHESTRATOR_MODEL = "ai21.jamba-1-5-large-v1:0"
bedrock = boto3.client(
    "bedrock-runtime",
    region_name=os.getenv("AWS_REGION", "us-east-1"),
    config=botocore.config.Config(connect_timeout=5, read_timeout=15),
)
DEBUG = False
MAX_TURNS = int(os.getenv("MAX_TURNS", "6"))
HISTORY_WINDOW = max(1, int(os.getenv("HISTORY_WINDOW", "10")))


# ==========================
# ENTRY POINT
# ==========================
def call_orchestrator(connection_id: str, apigw) -> None:
    """Entry point called from Lambda — orchestrates one round using only transcript memory."""
    tool_info = tool_specs()
    tools = tool_info["tool_config"]["tools"]
    specs = tool_info["specs"]

    system_prompt = build_system_prompt(specs)
    emitter = Emitter(apigw, connection_id)

    if DEBUG:
        emitter.debug_emit("Starting call_orchestrator", {"connection_id": connection_id})

    # Use the new helper to get history
    history: List[Dict[str, Any]] = build_history_messages(connection_id)

    ### this begins upon message sent from frontend
    for turn in range(MAX_TURNS):
        tool_result_blocks: List[Dict[str, Any]] = []

        if DEBUG:
            emitter.debug_emit("Turn: ", turn)
            # Log the size of the history being sent to the model for debugging context issues
            emitter.debug_emit("History Size: ", len(history))

        # Prepare payload for the converse call
        system_blocks = [{"text": system_prompt}]
        payload = {
            "modelId": ORCHESTRATOR_MODEL,
            "system": system_blocks,
            "messages": history,
            "toolConfig": {"tools": tools},
            "inferenceConfig": {"temperature": 0.5},
        }
        # Use the new JSON safe helper
        payload = to_native_json(payload)

        try:
            resp = bedrock.converse(**payload)
        except Exception as e:
            err = f"Model call failed: {e}"
            emitter.emit(err)
            # Use append_message_entry for error
            append_message_entry(
                connection_id,
                {"role": "assistant", "content": [{"text": err}]},
            )
            break

        # --- PROCESS MODEL RESPONSE ---

        # Use the new helper to save the assistant's response and get the last entry
        # This function handles splitting text/tool-use blocks and saving them to the database
        assistant_entry = save_assistant_from_bedrock_resp(connection_id, resp)
        content = assistant_entry.get("content") or []
        # Update in-memory history with the *last* saved entry (which should be the tool-use block if one exists)
        history.append(assistant_entry) 

        tool_uses = extract_tool_uses(content)
        assistant_texts = extract_text_chunks(content)

        # --- END OF TURN CHECK ---
        if not tool_uses:
            # If no tools, it's either the final answer or a nudge
            reply = "".join(assistant_texts).strip() 
            
            if reply or turn == MAX_TURNS - 1:
                # If we have a reply, or we've hit max turns, emit and break
                if reply:
                    emitter.emit(reply)
                break
            else:
                # Nudge for continuation if no text and no tools were returned, and we're not at max turns
                save_user_continue(connection_id)
                # The save_user_continue must be appended to history for the next model call
                history.append({"role": "user", "content": [{"text": "(continue)"}]})
                continue
        
        # --- TOOL EXECUTION AND RESULT PREP ---
        if DEBUG:
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
                preview_text = preview_tool_result(result)
            except Exception as e:
                err_payload = {"error": str(e)}
                preview_text = preview_tool_result(err_payload)
                emitter.emit(f"Tool {name} failed: {str(e)}")


            # Build the toolResult block
            tool_result_blocks.append({
                "toolResult": {
                    "toolUseId": tool_use_id,
                    "content": [{"text": preview_text}],
                }
            })

        # --- POST TOOL PROCESSING: Prepare for re-call ---
        
        # The original check for len(tool_result_blocks) > len(tool_uses) is redundant
        # here because tool_result_blocks is built 1:1 with tool_uses, but for safety:
        # if len(tool_result_blocks) > len(tool_uses):
        #     tool_result_blocks = tool_result_blocks[: len(tool_uses)]

        if tool_result_blocks:
            # Build the user message with tool results
            user_tool_result_entry = {"role": "user", "content": tool_result_blocks}
            
            if DEBUG:
                 emitter.debug_emit("Tool Results Ready. Re-calling model.","data")

            # Save the tool results to the database and update history
            # The save_user_tool_result_entry is critical to maintain the correct history state
            save_user_tool_result_entry(connection_id, tool_result_blocks)
            history.append(user_tool_result_entry)
            
            # The loop continues here, immediately re-calling the model 
            # with the tool results included in the history for the next turn.
            continue