import os, json, boto3, bcrypt

dynamodb = boto3.resource("dynamodb")
USERS_TABLE = os.environ.get("USERS_TABLE", "Users")
table = dynamodb.Table(USERS_TABLE)

def lambda_handler(event, context):
    body = json.loads(event["body"])
    email, old_pw, new_pw = body.get("email"), body.get("oldPassword"), body.get("newPassword")

    if not all([email, old_pw, new_pw]):
        return {"statusCode": 400, "body": "Missing fields"}

    response = table.scan(
        FilterExpression="email = :em",
        ExpressionAttributeValues={":em": email}, Limit=1
    )
    items = response.get("Items", [])
    if not items: return {"statusCode": 404, "body": "User not found"}

    user = items[0]
    if not bcrypt.checkpw(old_pw.encode(), user["password"].encode()):
        return {"statusCode": 401, "body": "Invalid credentials"}

    hashed_pw = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
    table.update_item(
        Key={"userId": user["userId"]},
        UpdateExpression="SET password = :pw",
        ExpressionAttributeValues={":pw": hashed_pw}
    )
    return {"statusCode": 200, "body": "Password updated"}
