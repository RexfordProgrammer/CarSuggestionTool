import os
import json
import requests
import boto3

# Note: save_bot_response is no longer needed in this file
# from db_tools import save_bot_response 

# Conservative size to stay well under API Gateway WS 32KB limit
_MAX_FRAME_BYTES = 28_000
DEBUG = True

def _safe_json(obj) -> str:
    """Safely serialize an object to a JSON string."""
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        return str(obj)


class Emitter:
    def __init__(self, apigw=None, connection_id=None, domain=None, stage=None):
        self.connection_id = connection_id
        self.is_local = os.getenv("AWS_SAM_LOCAL", "").lower() == "true"
        self.local_ws_url = (
            os.getenv("LOCAL_WS_URL")
            or ("http://host.docker.internal:8080" if self.is_local else None)
        )

        if self.local_ws_url:
            print(f"🧠 Local emit mode enabled → {self.local_ws_url}")
            self.apigw = None
        else:
            self.domain = domain or os.getenv("WS_DOMAIN")
            self.stage = stage or os.getenv("WS_STAGE")
            endpoint = os.getenv("WS_API_URL") or (f"https://{self.domain}/{self.stage}")
            self.apigw = apigw or boto3.client(
                "apigatewaymanagementapi",
                endpoint_url=endpoint,
            )
            print(f"🌐 Remote emit endpoint → {endpoint}")

    # --- helper to normalize text ---
    def _to_text(self, data) -> str:
        """Extract a readable string from any shape (dict, list, etc.)."""
        if data is None:
            return ""
        if isinstance(data, str):
            return data

        if isinstance(data, dict):
            # Check for common text keys
            for key in ("reply", "text", "message", "output"):
                val = data.get(key)
                if isinstance(val, str):
                    return val
            # Check for Bedrock-style content blocks
            if isinstance(data.get("content"), list):
                parts = []
                for c in data["content"]:
                    if isinstance(c, str):
                        parts.append(c)
                    elif isinstance(c, dict):
                        parts.append(c.get("text") or c.get("body") or _safe_json(c))
                return " ".join(p for p in parts if p)
            # Fallback for other dicts
            return _safe_json(data)

        if isinstance(data, (list, tuple)):
            return " ".join(self._to_text(i) for i in data)

        return str(data)

    # --- local send ---
    def _send_local(self, payload: dict) -> bool:
        """Sends payload to a local WebSocket server (e.g., SAM local)."""
        url = f"{self.local_ws_url}/@connections/{self.connection_id}"
        try:
            res = requests.post(url, json=payload, timeout=5)
            print(f"📨 [LOCAL EMIT] {res.status_code} → {url}")
            if res.status_code >= 400:
                print(f"❌ Local emit error body: {res.text[:500]}")
            return res.ok
        except Exception as e:
            print(f"❌ Local emit failed: {e}")
            return False

    # --- remote send ---
    def _send_remote(self, payload: dict) -> bool:
        """Sends payload to the deployed API Gateway WebSocket."""
        data_bytes = _safe_json(payload).encode("utf-8")
        try:
            self.apigw.post_to_connection(
                ConnectionId=self.connection_id,
                Data=data_bytes,
            )
            print(f"📨 [REMOTE EMIT] bytes={len(data_bytes)} to {self.connection_id}")
            return True
        except Exception as e:
            print(f"❌ Remote emit failed: {e}")
            return False

    # --- shared send ---
    def _send_payload(self, payload: dict) -> bool:
        """Send payload either locally or via API GW."""
        try:
            print("🪵 [FULL EMIT LOG] →", _safe_json(payload))
        except Exception as e:
            print(f"⚠️ Failed to log payload: {e}")

        if self.local_ws_url:
            return self._send_local(payload)
        return self._send_remote(payload)

    # ==========================================================
    # NORMAL EMIT (user-facing, NO persistence)
    # ==========================================================
    def emit(self, text) -> bool:
        """Emit to WebSocket (local or remote). ASSUMES message has already been persisted."""
        try:
            text_str = self._to_text(text).strip()
        except Exception as e:
            print(f"❌ Failed to coerce text: {e}, payload type={type(text)}")
            return False

        if not text_str:
            # Don't send empty messages
            return False

        print(f"\n🪵 [EMIT RAW TEXT - {len(text_str)} chars]\n{text_str}\n")
        
        #
        # 🛑 PERSISTENCE LOGIC REMOVED 🛑
        # The orchestrator (call_orchestrator) is now solely responsible 
        # for saving messages to the database via its helpers.
        #

        reply_bytes = text_str.encode("utf-8")
        chunks = []
        if len(reply_bytes) > _MAX_FRAME_BYTES:
            # Handle large messages by splitting them
            start = 0
            idx = 1
            total = (len(reply_bytes) + _MAX_FRAME_BYTES - 1) // _MAX_FRAME_BYTES
            while start < len(reply_bytes):
                end = min(start + _MAX_FRAME_BYTES, len(reply_bytes))
                chunk_text = reply_bytes[start:end].decode("utf-8", errors="ignore")
                chunks.append({
                    "type": "bedrock_reply",
                    "reply": f"[{idx}/{total}] {chunk_text}",
                })
                start = end
                idx += 1
        else:
            chunks.append({"type": "bedrock_reply", "reply": text_str})

        ok_all = True
        for payload in chunks:
            sent = self._send_payload(payload)
            ok_all = ok_all and sent
        return ok_all
    
    # ==========================================================
    # DEBUG EMIT (identical WS shape, no DB save)
    # ==========================================================
    def debug_emit(self, label: str, data) -> None:
        if (not DEBUG):
            return
        """Emit debug info to the chat the same way as normal output, but skip DynamoDB."""
        try:
            text = f"[DEBUG] {label}:\n" + json.dumps(data, indent=2, default=str)
        except Exception:
            text = f"[DEBUG] {label}:\n" + str(data)

        # console log
        print(f"\n🪵 {text}\n")

        # ---- send to WS exactly like emit(), but NO save_bot_response ----
        reply_bytes = text.encode("utf-8")
        chunks = []
        if len(reply_bytes) > _MAX_FRAME_BYTES:
            start = 0
            idx = 1
            total = (len(reply_bytes) + _MAX_FRAME_BYTES - 1) // _MAX_FRAME_BYTES
            while start < len(reply_bytes):
                end = min(start + _MAX_FRAME_BYTES, len(reply_bytes))
                chunk_text = reply_bytes[start:end].decode("utf-8", errors="ignore")
                chunks.append({
                    "type": "bedrock_reply",
                    "reply": f"[{idx}/{total}] {chunk_text}",
                })
                start = end
                idx += 1
        else:
            chunks.append({"type": "bedrock_reply", "reply": text})

        for payload in chunks:
            self._send_payload(payload)