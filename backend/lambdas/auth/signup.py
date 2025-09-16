import os, json, boto3, bcrypt, uuid
from datetime import datetime

dynamodb = boto3.resource("dynamodb")
USERS_TABLE = os.environ.get("USERS_TABLE", "Users")
table = dynamodb.Table(USERS_TABLE)

def lambda_handler(event, context):
    body = json.loads(event["body"])
    email, password = body.get("email"), body.get("password")

    if not email or not password:
        return {"statusCode": 400, "body": "Email and password required"}

    hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user_id = str(uuid.uuid4())

    table.put_item(Item={
        "userId": user_id, "email": email, "password": hashed_pw,
        "createdAt": datetime.utcnow().isoformat()
    })

    return {"statusCode": 201, "body": json.dumps({"userId": user_id, "email": email})}
