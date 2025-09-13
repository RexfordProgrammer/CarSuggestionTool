# cdk_py/ws_stack.py
import os
from aws_cdk import (Stack, Duration, CfnOutput)
from constructs import Construct
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_dynamodb as ddb
from aws_cdk import aws_iam as iam

import pathlib



class WsStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        table = ddb.Table(self, "CarFinderTable",
            table_name="CAR_FINDER_TABLE",
            partition_key=ddb.Attribute(name="pk", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="sk", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="ttl"
        )

        # --- REPLACE FROM HERE ---
        env = {"TABLE": table.table_name}

        # base directory that contains the lambdas folder, computed relative to this file
        THIS_FILE_DIR = pathlib.Path(__file__).resolve().parent  # .../backend/cdk_py
        LAMBDAS_BASE = (THIS_FILE_DIR / ".." / "lambdas").resolve()  # .../backend/lambdas

        def mk_fn(id: str, dir: str, reserved: int | None = None):
            asset_path = str((LAMBDAS_BASE / dir).resolve())
            fn_props = dict(
                runtime=_lambda.Runtime.NODEJS_20_X,
                handler="index.handler",
                code=_lambda.Code.from_asset(asset_path),
                timeout=Duration.seconds(15),
                memory_size=256,
                environment=env
            )
            if reserved is not None:
                fn_props["reserved_concurrent_executions"] = reserved

            return _lambda.Function(self, id, **fn_props)
        # --- TO HERE ---

        # Choose your caps here:
        on_connect = mk_fn("WsOnConnect", "ws-onconnect", reserved=2)
        on_message = mk_fn("WsOnMessage", "ws-onmessage", reserved=5)
        on_disconnect = mk_fn("WsOnDisconnect", "ws-ondisconnect", reserved=2)

        # grant lambdas access to the table
        table.grant_read_write_data(on_connect)
        table.grant_read_write_data(on_message)
        table.grant_read_write_data(on_disconnect)

        # Create the WebSocket API with route selection on "action" in request body
        ws_api = apigwv2.WebSocketApi(self, "CarFinderWsApi",
            api_name="car-finder-ws",
            route_selection_expression="$request.body.action"
        )

        # Integrate routes directly to lambdas (no authorizer)
        ws_api.add_route("$connect", integration=integrations.WebSocketLambdaIntegration("ConnectIntegration", on_connect))
        ws_api.add_route("$default", integration=integrations.WebSocketLambdaIntegration("MessageIntegration", on_message))
        ws_api.add_route("$disconnect", integration=integrations.WebSocketLambdaIntegration("DisconnectIntegration", on_disconnect))

        stage = apigwv2.WebSocketStage(self, "DevStage",
            web_socket_api=ws_api,
            stage_name="dev",
            auto_deploy=True
        )

        # Give the onMessage + onConnect permission to post back to clients
        manage = iam.PolicyStatement(actions=["execute-api:ManageConnections"],
            resources=[f"arn:aws:execute-api:{self.region}:{self.account}:{ws_api.api_id}/{stage.stage_name}/POST/@connections/*"])
        on_message.add_to_role_policy(manage)
        on_connect.add_to_role_policy(manage)

        CfnOutput(self, "WebSocketWssUrl", value=f"wss://{ws_api.api_id}.execute-api.{self.region}.amazonaws.com/{stage.stage_name}")
        CfnOutput(self, "TableName", value=table.table_name)
