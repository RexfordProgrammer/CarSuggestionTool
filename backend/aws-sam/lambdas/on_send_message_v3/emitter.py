import os, json, requests, boto3
from dynamo_db_helpers import save_bot_response

class Emitter:
    def __init__(self, apigw=None, connection_id=None, domain=None, stage=None):
        self.connection_id = connection_id
        # 👇 from a container, reach host on host.docker.internal
        self.is_local = os.getenv("AWS_SAM_LOCAL", "").lower() == "true"
        self.local_ws_url = (
            os.getenv("LOCAL_WS_URL")
            or ("http://host.docker.internal:8080" if self.is_local else None)
        )

        print("CHECKING FOR LOCAL RUN OR NOT")
        print("DEBUG ENV:", dict(os.environ))

        if self.local_ws_url:
            print(f"🧠 Local emit mode enabled → {self.local_ws_url}")
        else:
            self.domain = domain or os.getenv("WS_DOMAIN")
            self.stage = stage or os.getenv("WS_STAGE")
            endpoint = os.getenv("WS_API_URL") or f"https://{self.domain}/{self.stage}"
            self.apigw = apigw or boto3.client("apigatewaymanagementapi", endpoint_url=endpoint)

    def emit(self, text: str):
        text = (text or "").strip()
        if not text:
            return

        payload = {"type": "bedrock_reply", "reply": text}
        save_bot_response(text, self.connection_id)

        if self.local_ws_url:
            try:
                url = f"{self.local_ws_url}/@connections/{self.connection_id}"
                res = requests.post(url, json=payload, timeout=3)
                print(f"📨 [LOCAL EMIT] {res.status_code} → {url}")
            except Exception as e:
                print(f"❌ Local emit failed: {e}")
            return

        # AWS path
        try:
            self.apigw.post_to_connection(
                ConnectionId=self.connection_id,
                Data=json.dumps(payload).encode("utf-8")
            )
        except Exception as e:
            print(f"❌ Emit failed: {e}")
