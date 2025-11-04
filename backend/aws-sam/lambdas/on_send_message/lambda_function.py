import boto3
import json

from dynamo_db_helpers import save_user_message 
from call_bedrock_conversational import get_model_response 


def push_message_to_caller(connection_id, apigw, message):
    ## this is just a package to return to frontend
    ## TODO Think about refactoring bedrock reply to backend_reply
    payload = {"type": "bedrock_reply", "reply": message}

    ## ATTEMPT TO RETURN PAYLOAD TO CALLER ##
    try:
        ### This is where we are "Trying" to push messages wot the window
        apigw.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(payload).encode("utf-8")
        )
        print("Sent successfully")
    except Exception as e:
        print("Error posting to connection:", str(e))

def lambda_handler(event, context):
    print("Full event:", json.dumps(event))
    # Session Identifier
    connection_id = event["requestContext"]["connectionId"]
    # API Domain name 
    domain = event["requestContext"]["domainName"]
    stage = event["requestContext"]["stage"]

    try:
        body = json.loads(event.get("body") or "{}")
    except Exception as e:
        print("Error parsing body:", e)
        body = {}

    user_message = body.get("text", "(no text)")
    # this passes the user message to the DB for model context
    save_user_message(user_message, connection_id)

    backend_response = "(no output)"
    ## SINCE THE message has already been passed to the backend 
    ## THE DB to be saved, simply requests the next message in the 
    ## Sequence for the
    backend_response = get_model_response(connection_id)
    
    ## This is just setting up the connection which will end up passing the information back to the user 
    
    #######################################################
    ## We can call this object multiple times from this context ## 
    ########################################################
    apigw = boto3.client("apigatewaymanagementapi", endpoint_url=f"https://{domain}/{stage}")

    ### this is pushing the message, however if we change the conversational prompt to add a 
    ### trigger phrase to the output like "Hold on while we gather those reccomendations for you...." 
    ### like some unique sequence out of this which we use to actually trigger a different action like 
    ### "Go to x helper and fire get_reccomended_vehicles" then return that into the prompt 
    ### and call_bedrock then push_to_caller"
    push_message_to_caller(connection_id,apigw,backend_response)


    ## We should only allow this send message to end once all the logic is complete
    return {"statusCode": 200}
