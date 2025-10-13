# ----- settings -----
$ErrorActionPreference = "Stop"
$Region      = "us-east-1"
$AccountId   = "661364632619"
$RoleName    = "lambda-basic-execution-role"
$Function    = "HelloWorld"
$ApiName     = "HelloWorldAPI"
$ZipPath     = "function.zip"

# Always operate in the allowed region
aws configure set region $Region | Out-Null

# ----- create trust policy as an object and serialize to JSON safely -----
$trustObj = @{
  Version = "2012-10-17"
  Statement = @(
    @{
      Effect    = "Allow"
      Principal = @{ Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }
  )
}

$createRoleSpec = @{
  RoleName                 = $RoleName
  AssumeRolePolicyDocument = $trustObj
}

# Write CLI input JSON to a file (avoids quoting issues completely)
$roleSpecFile = "create-role.json"
$createRoleSpec | ConvertTo-Json -Depth 10 | Set-Content -Encoding utf8 $roleSpecFile

# ----- create role (idempotent-ish) -----
try {
  aws iam create-role --cli-input-json file://$roleSpecFile | Out-Null
} catch {
  if ($_.Exception.Message -notmatch "EntityAlreadyExists") { throw }
  Write-Host "Role '$RoleName' already exists, continuing..."
}

# Attach basic execution policy for CloudWatch Logs
aws iam attach-role-policy `
  --role-name $RoleName `
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole | Out-Null

# IAM is eventually consistent; short wait prevents race conditions
Start-Sleep -Seconds 8

# ----- create hello world lambda source -----
@'
def lambda_handler(event, context):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": "{\"message\": \"Hello, world!\"}"
    }
'@ | Set-Content -Encoding utf8 helloworld.py

# Package
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
Compress-Archive -Path helloworld.py -DestinationPath $ZipPath -Force

# ----- create (or update) the Lambda function -----
$roleArn = "arn:aws:iam::$AccountId:role/$RoleName"
try {
  aws lambda create-function `
    --function-name $Function `
    --runtime python3.12 `
    --role $roleArn `
    --handler helloworld.lambda_handler `
    --zip-file fileb://$ZipPath `
    --region $Region | Out-Null
} catch {
  if ($_.Exception.Message -match "ResourceConflictException") {
    aws lambda update-function-code `
      --function-name $Function `
      --zip-file fileb://$ZipPath `
      --region $Region | Out-Null
  } else {
    throw
  }
}

# ----- create an HTTP API and integrate the Lambda -----
$lambdaArn = "arn:aws:lambda:${Region}:${AccountId}:function:${Function}"
$api = aws apigatewayv2 create-api `
  --name $ApiName `
  --protocol-type HTTP `
  --target $lambdaArn `
  --region $Region | ConvertFrom-Json

$apiId = $api.ApiId
$endpoint = $api.ApiEndpoint

# Allow API Gateway to invoke the Lambda
aws lambda add-permission `
  --function-name $Function `
  --statement-id apigwinvoke `
  --action lambda:InvokeFunction `
  --principal apigateway.amazonaws.com `
  --source-arn "arn:aws:execute-api:${Region}:${AccountId}:$apiId/*/*" `
  --region $Region | Out-Null

Write-Host ""
Write-Host "✅ Deployed!"
Write-Host "Invoke URL: $endpoint"
Write-Host "Try:  Invoke-RestMethod -Uri $endpoint"
