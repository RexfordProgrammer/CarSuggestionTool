
import os
import random
import string
from typing import List
os.environ["AWS_REGION"] = "us-east-1"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
from db_tools_v2 import save_user_message
from bedrock_caller_v2 import call_orchestrator

def generate_random_string(length: int = 10) -> str:
    characters: str = string.ascii_letters
    random_chars: List[str] = [random.choice(characters) for _ in range(length)]
    random_string: str = "".join(random_chars)
    
    return random_string

# ==========================
# LOCAL TEST HARNESS
# ==========================
if __name__ == "__main__":
    test_connection_id = generate_random_string()
    class DummyApiGw:
        def post_to_connection(self, ConnectionId, Data):
            print("\n")

    dummy_apigw = DummyApiGw()
    
    while (True):
        somebs = input("\nUser:")
        save_user_message( test_connection_id, somebs)
        call_orchestrator(test_connection_id, dummy_apigw)