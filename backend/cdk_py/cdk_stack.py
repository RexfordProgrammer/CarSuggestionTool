from aws_cdk import (
    core,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_integrations as apigwv2_int,
    aws_dynamodb as ddb,
)

class MyStack(core.Stack):
    def __init__(self, scope: core.Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # DynamoDB Users table
        users_table = ddb.Table(
            self, "UsersTable",
            partition_key={"name": "userId", "type": ddb.AttributeType.STRING}
        )

        # Signup Lambda
        signup_fn = _lambda.Function(
            self, "SignupFn",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="signup.lambda_handler",
            code=_lambda.Code.from_asset("lambdas/auth"),
            environment={"USERS_TABLE": users_table.table_name}
        )
        users_table.grant_read_write_data(signup_fn)

        # API Gateway REST for Auth
        api = apigw.RestApi(self, "AuthAPI")
        auth = api.root.add_resource("auth")
        auth.add_resource("signup").add_method("POST", apigw.LambdaIntegration(signup_fn))

        # WebSocket API
        ws_api = apigwv2.WebSocketApi(self, "WsApi")

        ws_on_message = _lambda.Function(
            self, "WsOnMessage",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="on_message.lambda_handler",
            code=_lambda.Code.from_asset("lambdas/ws"),
            environment={"WS_ENDPOINT": ws_api.api_endpoint}
        )

        ws_on_disconnect = _lambda.Function(
            self, "WsOnDisconnect",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="on_disconnect.lambda_handler",
            code=_lambda.Code.from_asset("lambdas/ws")
        )

        ws_api.add_route("message", integration=apigwv2_int.WebSocketLambdaIntegration("MessageIntegration", ws_on_message))
        ws_api.add_route("$disconnect", integration=apigwv2_int.WebSocketLambdaIntegration("DisconnectIntegration", ws_on_disconnect))

        apigwv2.WebSocketStage(self, "ProdStage", web_socket_api=ws_api, stage_name="prod", auto_deploy=True)
