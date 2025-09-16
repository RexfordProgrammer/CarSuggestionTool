from aws_cdk import aws_apigateway as apigw

# Auth Lambdas
signup_fn = _lambda.Function(
    self, "SignupFn",
    runtime=_lambda.Runtime.PYTHON_3_12,
    handler="signup.lambda_handler",
    code=_lambda.Code.from_asset(str(LAMBDAS_BASE / "auth")),
    environment={"USERS_TABLE": table.table_name}
)
login_fn = _lambda.Function(
    self, "LoginFn",
    runtime=_lambda.Runtime.PYTHON_3_12,
    handler="login.lambda_handler",
    code=_lambda.Code.from_asset(str(LAMBDAS_BASE / "auth")),
    environment={"USERS_TABLE": table.table_name, "JWT_SECRET": "supersecret"}  # use Secrets Manager in prod
)
change_pw_fn = _lambda.Function(
    self, "ChangePasswordFn",
    runtime=_lambda.Runtime.PYTHON_3_12,
    handler="change_password.lambda_handler",
    code=_lambda.Code.from_asset(str(LAMBDAS_BASE / "auth")),
    environment={"USERS_TABLE": table.table_name}
)

table.grant_read_write_data(signup_fn)
table.grant_read_data(login_fn)
table.grant_read_write_data(change_pw_fn)

# REST API
api = apigw.RestApi(self, "AuthAPI")
auth = api.root.add_resource("auth")
auth.add_resource("signup").add_method("POST", apigw.LambdaIntegration(signup_fn))
auth.add_resource("login").add_method("POST", apigw.LambdaIntegration(login_fn))
auth.add_resource("change_password").add_method("POST", apigw.LambdaIntegration(change_pw_fn))
