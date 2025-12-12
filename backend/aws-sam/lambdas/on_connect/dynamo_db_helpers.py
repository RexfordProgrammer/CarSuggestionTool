import boto3
import json

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("messages")
preferenceTable = dynamodb.Table("session-preferences")

def initialize_session_messages(connection_id):
    table.put_item(
        Item={
            "connectionId": connection_id,
            "messages": [],
        }
    )
