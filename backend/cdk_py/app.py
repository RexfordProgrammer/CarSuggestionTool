#!/usr/bin/env python3
import os
import aws_cdk as cdk

# since app.py and ws_stack.py are in the same directory, import directly
from ws_stack import WsStack

app = cdk.App()
WsStack(app, "CarFinderWsDev",
       env=cdk.Environment(account=os.getenv("CDK_DEFAULT_ACCOUNT"),
                           region=os.getenv("CDK_DEFAULT_REGION")))
app.synth()
