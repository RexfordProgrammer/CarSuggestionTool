
import json
from dynamo_db_helpers import (
    save_bot_response
)

class Emitter:
    def __init__(self, apigw, connection_id):
        self.apigw = apigw
        self.connection_id = connection_id

    def emit(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        payload = {"type": "bedrock_reply", "reply": text}
        try:
            self.apigw.post_to_connection(
                ConnectionId=self.connection_id,
                Data=json.dumps(payload).encode("utf-8"),
            )
            print(f"✅ Sent to {self.connection_id}: {payload}")
        except self.apigw.exceptions.GoneException:
            print(f"⚠️ Connection {self.connection_id} gone.")
        except Exception as e:
            print(f"❌ Emit failed: {e}")
        else:
            save_bot_response(text, self.connection_id)
