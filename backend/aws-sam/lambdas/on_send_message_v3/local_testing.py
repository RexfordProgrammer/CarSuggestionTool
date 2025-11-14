""" This is just a simple local tester which sets some envs and runs orchestrator"""
import os
import random
import string
from typing import List
os.environ["AWS_REGION"] = "us-east-1"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
from db_tools_v2 import save_user_message #pylint: disable=wrong-import-position
from bedrock_caller_v2 import call_orchestrator #pylint: disable=wrong-import-position




def generate_random_string(length: int = 10) -> str:
    """Generates a random token for connecting to dynamodb"""
    characters: str = string.ascii_letters
    random_chars: List[str] = [random.choice(characters) for _ in range(length)]
    random_string: str = "".join(random_chars)
    return random_string

# ==========================
# LOCAL TEST HARNESS
# ==========================
if __name__ == "__main__":
    TEST_CONNECTION_ID = generate_random_string()
    class DummyApiGw:
        """Dummy object for reqs"""
        def post_to_connection(self, ConnectionId, Data): #TODO fix case issues this in emitter and here
            """This is just a dummy to satisfy the req"""

    dummy_apigw = DummyApiGw()
    while True:
        somebs = input("\nUser:")
        save_user_message( TEST_CONNECTION_ID, somebs)
        call_orchestrator(TEST_CONNECTION_ID, dummy_apigw)