
import os
os.environ["AWS_REGION"] = "us-east-1"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
from db_tools_v2 import save_user_message
from bedrock_caller_v2 import call_orchestrator
# ==========================
# LOCAL TEST HARNESS
# ==========================
if __name__ == "__main__":
    test_connection_id = "LOCAL_TEST_CONNECTION"

    save_user_message( test_connection_id, "(connected)")
    # Simple dummy ApiGatewayManagementApi client for local testing
    class DummyApiGw:
        def post_to_connection(self, ConnectionId, Data):
            print(f"[DummyApiGw] post_to_connection → {ConnectionId}")
            try:
                print(Data.decode("utf-8")[:500])
            except Exception:
                print(repr(Data)[:500])

    dummy_apigw = DummyApiGw()

    call_orchestrator(test_connection_id, dummy_apigw)
    
    while (True):
        somebs = input("Enter")
        save_user_message( test_connection_id, somebs)
        call_orchestrator(test_connection_id, dummy_apigw)