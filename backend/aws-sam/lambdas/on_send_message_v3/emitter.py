# emitter.py
import os, json, requests, boto3
from dynamo_db_helpers import save_bot_response

# Conservative size to stay well under API Gateway WS 32KB limit
_MAX_FRAME_BYTES = 28_000

def _safe_json(obj) -> str:
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
            # Common textual keys
            for key in ("reply", "text", "message", "output"):
                val = data.get(key)
                if isinstance(val, str):
                    return val
            # Bedrock-style message content
            if isinstance(data.get("content"), list):
                parts = []
                for c in data["content"]:
                    if isinstance(c, str):
                        parts.append(c)
                    elif isinstance(c, dict):
                        # Try text-ish fields then fall back to json
                        parts.append(c.get("text") or c.get("body") or _safe_json(c))
                return " ".join(p for p in parts if p)
            # Fallback: stringify whole object
            return _safe_json(data)

        if isinstance(data, (list, tuple)):
            return " ".join(self._to_text(i) for i in data)

        return str(data)

    def _send_local(self, payload: dict) -> bool:
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

    def _send_remote(self, payload: dict) -> bool:
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

    def _send_payload(self, payload: dict) -> bool:
        """Send payload either locally or via API GW."""
        if self.local_ws_url:
            return self._send_local(payload)
        return self._send_remote(payload)

    def emit(self, text) -> bool:
        """Emit to WebSocket (local or remote). Returns True on success."""
        try:
            text_str = self._to_text(text).strip()
        except Exception as e:
            print(f"❌ Failed to coerce text: {e}, payload type={type(text)}")
            return False

        if not text_str:
            # Nothing to send
            return False

        # Persist, but don't let failures block sending
        try:
            save_bot_response(text_str, self.connection_id)
        except Exception as e:
            print(f"⚠️ save_bot_response failed (continuing): {e}")

        # Frame-size guard & chunking
        # Note: We chunk the 'reply' only; the wrapper JSON is tiny.
        # Keep chunks aligned to byte limit, not char count.
        reply_bytes = text_str.encode("utf-8")
        chunks = []
        if len(reply_bytes) > _MAX_FRAME_BYTES:
            # Split into multiple frames
            start = 0
            idx = 1
            total = (len(reply_bytes) + _MAX_FRAME_BYTES - 1) // _MAX_FRAME_BYTES
            while start < len(reply_bytes):
                end = min(start + _MAX_FRAME_BYTES, len(reply_bytes))
                chunk_text = reply_bytes[start:end].decode("utf-8", errors="ignore")
                payload = {
                    "type": "bedrock_reply",
                    "reply": f"[{idx}/{total}] {chunk_text}",
                }
                chunks.append(payload)
                start = end
                idx += 1
        else:
            chunks.append({"type": "bedrock_reply", "reply": text_str})

        ok_all = True
        for payload in chunks:
            sent = self._send_payload(payload)
            ok_all = ok_all and sent
        return ok_all
