
import os
import random
import string
from typing import List
os.environ["AWS_REGION"] = "us-east-1"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
from db_tools_v2 import save_user_message
from bedrock_caller_v2 import call_orchestrator

def generate_random_string(length: int = 10) -> str:
    """
    Generates a random string of specified length containing only letters (a-z, A-Z).

    Args:
        length: The desired length of the random string. Defaults to 10.

    Returns:
        A randomly generated string of letters.
    """
    # Define the pool of characters: all lowercase and uppercase letters
    characters: str = string.ascii_letters
    
    # Use random.choice() to pick a character for 'length' number of times
    random_chars: List[str] = [random.choice(characters) for _ in range(length)]
    
    # Join the list of characters into a single string
    random_string: str = "".join(random_chars)
    
    return random_string

# ==========================
# LOCAL TEST HARNESS
# ==========================
if __name__ == "__main__":
    test_connection_id = generate_random_string()
    # Simple dummy ApiGatewayManagementApi client for local testing
    class DummyApiGw:
        def post_to_connection(self, ConnectionId, Data):
            print("\n")

    dummy_apigw = DummyApiGw()
    
    while (True):
        somebs = input("\nUser:")
        save_user_message( test_connection_id, somebs)
        call_orchestrator(test_connection_id, dummy_apigw)