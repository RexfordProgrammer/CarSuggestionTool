"""This file manages emmissions to API"""
import json
from typing import Any, Literal
import boto3
from pydantic import BaseModel

class WebSocketPayload(BaseModel):
    """Model for the data sent over the WebSocket."""
    type: Literal["bedrock_reply"]
    reply: str

_MAX_FRAME_BYTES = 28_000

def _safe_json(obj: Any) -> str:
    """Safely serialize an object to a JSON string."""
    try:
        if isinstance(obj, BaseModel):
            return obj.model_dump_json(exclude_none=True)
        return json.dumps(obj, ensure_ascii=False, default=str)
    except Exception: #pylint: disable=broad-exception-caught
        return str(obj)

class Emitter:
    """Handles sending messages to the connected client via API Gateway WebSocket."""

    def __init__(self, apigw: boto3.client, connection_id: str, debug: bool = True):
        self.debug = debug
        self.connection_id = connection_id
        if apigw is None:
            raise ValueError("API Gateway client (apigw)"
                             "must be provided in a non-local environment.")
        self.apigw = apigw

    def _to_text(self, data: Any) -> str:
        """Extract a readable string from any shape (Pydantic model, dict, list, etc.)."""
        if data is None:
            return ""
        if isinstance(data, str):
            return data
        if isinstance(data, BaseModel):
            data = data.model_dump()
        if isinstance(data, dict):
            for key in ("reply", "text", "message", "output"):
                val = data.get(key)
                if isinstance(val, str):
                    return val
            if isinstance(data.get("content"), list):
                parts = []
                for c in data["content"]:
                    if isinstance(c, str):
                        parts.append(c)
                    elif isinstance(c, dict):
                        parts.append(c.get("text") or _safe_json(c))
                return " ".join(p for p in parts if p)
            return _safe_json(data)

        if isinstance(data, (list, tuple)):
            return " ".join(self._to_text(i) for i in data)

        return str(data)

    def _send_remote(self, payload: WebSocketPayload) -> bool:
        """Sends payload to the deployed API Gateway WebSocket."""
        data_bytes = payload.model_dump_json(exclude_none=True).encode("utf-8")
        try:
            self.apigw.post_to_connection(
                ConnectionId=self.connection_id,
                Data=data_bytes,
            )
            return True
        except Exception as e: #pylint: disable=broad-exception-caught
            print(f"Remote emit failed (Connection ID: {self.connection_id}): {e}")
            return False

    # --- shared send (internal) ---
    def _send_payload(self, payload: WebSocketPayload) -> bool:
        """Send payload via API GW, logging the action."""
        return self._send_remote(payload)

    # ==========================================================
    # NORMAL EMIT (user-facing, NO persistence)
    # ==========================================================
    def emit(self, text: Any) -> bool:
        """Emit user-facing text to the WebSocket."""
        try:
            text_str = self._to_text(text).strip()
        except Exception as e: #pylint: disable=broad-exception-caught
            print(f"❌ Failed to coerce text: {e}, payload type={type(text)}")
            return False

        if not text_str:
            return False
        print(f"[EMIT RAW TEXT - chars]\n{text_str}\n")

        reply_bytes = text_str.encode("utf-8")
        chunks = []
        # Handle large messages by splitting into chunks
        if len(reply_bytes) > _MAX_FRAME_BYTES:
            start = 0
            idx = 1
            total = (len(reply_bytes) + _MAX_FRAME_BYTES - 1) // _MAX_FRAME_BYTES
            while start < len(reply_bytes):
                end = min(start + _MAX_FRAME_BYTES, len(reply_bytes))
                chunk_text = reply_bytes[start:end].decode("utf-8", errors="ignore")
                # FIX APPLIED HERE for chunked message:
                chunks.append(
                    WebSocketPayload(type="bedrock_reply", reply=f"[{idx}/{total}] {chunk_text}")
                )
                start = end
                idx += 1
        else:
            # FIX APPLIED HERE for single message:
            chunks.append(WebSocketPayload(type="bedrock_reply", reply=text_str))

        ok_all = True
        for payload in chunks:
            sent = self._send_payload(payload)
            ok_all = ok_all and sent
        return ok_all

    # ==========================================================
    # DEBUG EMIT (identical WS shape, no DB save)
    # ==========================================================
    def debug_emit(self, label: str, data: Any) -> None:
        """Emit debug info to the chat."""
        if not self.debug:
            return
        try:
            serialized_data = json.dumps(data, indent=2, default=str)
            text = f"[DEBUG] {label}:\n" + serialized_data
        except Exception: #pylint: disable=broad-exception-caught
            text = f"[DEBUG] {label}:\n" + str(data)

        print(f"\n Log: {text}\n")
        reply_bytes = text.encode("utf-8")
        chunks = []
        if len(reply_bytes) > _MAX_FRAME_BYTES:
            start = 0
            idx = 1
            total = (len(reply_bytes) + _MAX_FRAME_BYTES - 1) // _MAX_FRAME_BYTES
            while start < len(reply_bytes):
                end = min(start + _MAX_FRAME_BYTES, len(reply_bytes))
                chunk_text = reply_bytes[start:end].decode("utf-8", errors="ignore")
                chunks.append(
                    WebSocketPayload(type="bedrock_reply", reply=f"[{idx}/{total}] {chunk_text}")
                )
                start = end
                idx += 1
        else:
            chunks.append(WebSocketPayload(type="bedrock_reply", reply=text))

        for payload in chunks:
            self._send_payload(payload)
