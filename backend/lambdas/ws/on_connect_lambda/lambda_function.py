def lambda_handler(event, context):
    print("Connect event:", event)
    return {
        "statusCode": 200,
        "body": "Connected"
    }
