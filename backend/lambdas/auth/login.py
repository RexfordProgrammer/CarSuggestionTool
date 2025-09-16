import os, json, boto3, bcrypt, jwt
from datetime import datetime, timedelta

dynamodb = boto3.resource("dynamodb")
USERS_TABLE = os.environ.get("USERS_TABLE", "Users")
table = dynamodb.Table(USERS_TABLE)
JWT_SECRET = os.environ.get("JWT_SECRET", "supersecret")

def lambda_handler(event, context):
    body = json.loads(event["body"])
    email, password = body.get("email"), body.get("password")

    response = table.scan(
        FilterExpression="email = :em",
        ExpressionAttributeValues={":em": email}, Limit=1
    )
    items = response.get("Items", [])
    if not items: return {"statusCode": 401, "body": "Invalid credentials"}

    user = items[0]
    if not bcrypt.checkpw(password.encode(), user["password"].encode()):
        return {"statusCode": 401, "body": "Invalid credentials"}

    token = jwt.encode(
        {"sub": user["userId"], "email": user["email"], "exp": datetime.utcnow() + timedelta(hours=1)},
        JWT_SECRET, algorithm="HS256"
    )
    return {"statusCode": 200, "body": json.dumps({"token": token})}
